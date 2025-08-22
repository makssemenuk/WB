import os
import re
import aiohttp
import asyncio
from typing import Optional, Tuple
from urllib.parse import urlparse, parse_qs


class WildberriesPriceParser:
    def __init__(self):
        self.session = None
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36',
            'Referer': 'https://www.wildberries.ru/'
        }
        # Опциональный прокси из окружения
        self.proxy_url = os.getenv('WB_PROXY_URL') or os.getenv('HTTP_PROXY') or os.getenv('HTTPS_PROXY')

    async def __aenter__(self):
        # trust_env=True позволит aiohttp использовать системные прокси, если они заданы
        self.session = aiohttp.ClientSession(headers=self.headers, trust_env=True)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()

    def extract_product_id(self, url: str) -> Optional[str]:
        """Извлекает ID товара из URL Wildberries"""
        try:
            # Если просто число
            if url.isdigit():
                return url

            patterns = [
                r'/catalog/(\d+)/detail\.aspx',           # /catalog/93378993/detail.aspx
                r'/catalog/(\d+)/?$',                      # /catalog/93378993
                r'/catalog/(\d+)/(?:[^/]+/)*$',            # /catalog/93378993/<...>
                r'/product/(\d+)/',                        # /product/93378993/
                r'card/(\d+)',                             # ...card/93378993
                r'(\d+)\.html'                            # .../93378993.html
            ]
            
            for pattern in patterns:
                match = re.search(pattern, url)
                if match:
                    return match.group(1)
            
            parsed = urlparse(url)
            query_params = parse_qs(parsed.query)
            if 'nm' in query_params and len(query_params['nm']) > 0:
                return query_params['nm'][0]
            
            return None
        except Exception:
            return None

    def _calc_vol_part(self, product_id: int) -> Tuple[int, int]:
        # Формула для legacy basket JSON
        vol = product_id // 100000
        part = product_id // 1000
        return vol, part

    async def _http_get_json(self, url: str) -> Optional[dict]:
        try:
            async with self.session.get(url, proxy=self.proxy_url, timeout=aiohttp.ClientTimeout(total=15)) as response:
                if response.status != 200:
                    return None
                return await response.json(content_type=None)
        except Exception:
            return None

    async def _try_cards_v2(self, product_id: str) -> Optional[Tuple[str, float]]:
        api_url = (
            f"https://card.wb.ru/cards/v2/detail?appType=1&curr=rub&dest=-1257786&spp=0&nm={product_id}"
        )
        data = await self._http_get_json(api_url)
        if not data:
            return None
        products = data.get('data', {}).get('products', [])
        if not products:
            return None
        product = products[0]
        name = product.get('name') or 'Неизвестный товар'
        price_cents = None
        if isinstance(product.get('salePriceU'), (int, float)):
            price_cents = product['salePriceU']
        elif isinstance(product.get('priceU'), (int, float)):
            price_cents = product['priceU']
        else:
            if 'sizes' in product and product['sizes']:
                for size in product['sizes']:
                    price_obj = size.get('price') or {}
                    if 'product' in price_obj:
                        price_cents = price_obj['product']
                        break
        if price_cents is None:
            return None
        return name, float(price_cents) / 100.0

    async def _try_cards_v1(self, product_id: str) -> Optional[Tuple[str, float]]:
        api_url = f"https://card.wb.ru/cards/detail?nm={product_id}"
        data = await self._http_get_json(api_url)
        if not data:
            return None
        products = data.get('data', {}).get('products', [])
        if not products:
            return None
        product = products[0]
        name = product.get('name') or 'Неизвестный товар'
        price = None
        if 'sizes' in product and product['sizes']:
            for size in product['sizes']:
                price_obj = size.get('price') or {}
                if 'product' in price_obj:
                    price = price_obj['product'] / 100.0
                    break
        if price is None:
            return None
        return name, price

    async def _try_basket_json(self, product_id: str) -> Optional[Tuple[str, float]]:
        try:
            pid = int(product_id)
        except ValueError:
            return None
        vol, part = self._calc_vol_part(pid)
        # basket-0..31 – обычно достаточно 01..32, попробуем несколько
        for i in range(1, 6):
            host = f"https://basket-{i:02d}.wb.ru/vol{vol}/part{part}/{pid}/info/ru/card.json"
            data = await self._http_get_json(host)
            if not data:
                continue
            name = data.get('imt_name') or data.get('subj_name') or 'Неизвестный товар'
            # Цена в копейках
            price_cents = data.get('salePriceU') or data.get('priceU')
            if isinstance(price_cents, (int, float)):
                return name, float(price_cents) / 100.0
            # Альтернативные поля
            if isinstance(data.get('price'), (int, float)):
                return name, float(data['price']) / 100.0
        return None

    async def get_product_info(self, url: str) -> Optional[Tuple[str, float]]:
        """Получает информацию о товаре: название и цену"""
        try:
            product_id = self.extract_product_id(url)
            if not product_id:
                return None

            # Пытаемся в порядке: v2 -> v1 -> basket
            for fetcher in (self._try_cards_v2, self._try_cards_v1, self._try_basket_json):
                result = await fetcher(product_id)
                if result:
                    return result

            return None
        except Exception as e:
            print(f"Ошибка при получении информации о товаре: {e}")
            return None

    async def check_price(self, url: str) -> Optional[float]:
        """Проверяет текущую цену товара"""
        try:
            result = await self.get_product_info(url)
            if result:
                return result[1]
            return None
        except Exception as e:
            print(f"Ошибка при проверке цены: {e}")
            return None


# Функция для удобного использования
async def get_wildberries_price(url: str) -> Optional[Tuple[str, float]]:
    """Удобная функция для получения цены и названия товара с Wildberries"""
    async with WildberriesPriceParser() as parser:
        return await parser.get_product_info(url)


async def check_wildberries_price(url: str) -> Optional[float]:
    """Удобная функция для проверки цены товара с Wildberries"""
    async with WildberriesPriceParser() as parser:
        return await parser.check_price(url)
