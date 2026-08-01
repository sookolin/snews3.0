"""
Test parse: one source per city, fetch one item.
Run: docker exec citynews-backend-1 python /app/scripts/test_parse_cities.py
"""
import asyncio, traceback

CITY_SOURCES = {
    5:  (31,  "Краснодар",  "Кубанские новости RSS"),
    7:  (50,  "Тимашевск",  "Тимашевск.ру WEBSITE"),
    10: (60,  "Одинцово",   "Одинцово Инфо RSS"),
    11: (52,  "Домодедово", "Домодедово 24 TG"),
    12: (64,  "Химки",      "Химки.нет WEBSITE"),
    13: (66,  "Егорьевск",  "Егорьевск Новости TG"),
}

async def test_source(source_id: int, city_name: str, label: str):
    from shared.database import session_scope
    from shared.models.source import Source
    from shared.plugins.parsers import parser_registry

    print(f"\n{'='*64}")
    print(f"  Город: {city_name}  |  {label}  (id={source_id})")
    print(f"{'='*64}")
    try:
        async with session_scope() as session:
            src = await session.get(Source, source_id)
            if src is None:
                print("  ❌  Источник не найден в БД")
                return
            print(f"  URL/handle : {src.url}")
            print(f"  Тип        : {src.type.value}")
            print(f"  Активен    : {src.is_active}")
            print(f"  Ошибок     : {src.error_count}")

            if not parser_registry.has(src.type.value):
                print(f"  ❌  Нет парсера для типа {src.type.value}")
                return

            parser = parser_registry.get(src.type.value)(src)
            try:
                items = await parser.fetch()
            except Exception as e:
                print(f"  ❌  Ошибка fetch: {e}")
                return

            if not items:
                print("  ⚠️  Нет элементов (пустой фид или канал недоступен)")
                return

            item = items[0]
            print(f"  ✅  Получено элементов: {len(items)}, показываю первый:")
            title = getattr(item, 'title', None) or ''
            url   = getattr(item, 'url', None) or getattr(item, 'link', None) or ''
            text  = getattr(item, 'text', None) or getattr(item, 'body', None) or ''
            pub   = getattr(item, 'published_at', None) or ''
            print(f"      Заголовок : {str(title)[:110]}")
            print(f"      URL       : {str(url)[:110]}")
            print(f"      Дата      : {pub}")
            snippet = str(text)[:200].replace('\n', ' ')
            print(f"      Текст     : {snippet}…" if len(str(text)) > 200 else f"      Текст     : {snippet}")
    except Exception:
        traceback.print_exc()

async def main():
    print("\n🔍 Тестовый парсинг — по одному источнику на каждый город\n")
    for city_id, (src_id, city_name, lbl) in CITY_SOURCES.items():
        await test_source(src_id, city_name, lbl)
    print(f"\n{'='*64}")
    print("  Готово.")
    print(f"{'='*64}\n")

asyncio.run(main())
