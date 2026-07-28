"use client";

import { useMemo, useState } from "react";
import { Smile, X, Search } from "lucide-react";

/**
 * Emoji catalogue with Russian keywords for search.
 *
 * Kept as a curated list (not the full Unicode set) so the bundle stays small
 * while covering everything a news channel realistically needs.
 */
const EMOJI: { char: string; keywords: string }[] = [
  // News / attention
  { char: "🔥", keywords: "огонь горячее срочно важно" },
  { char: "⚡️", keywords: "молния быстро срочно энергия свет" },
  { char: "🚨", keywords: "сирена срочно авария полиция чп" },
  { char: "❗️", keywords: "восклицание важно внимание" },
  { char: "‼️", keywords: "важно внимание двойное" },
  { char: "📢", keywords: "объявление громкоговоритель анонс" },
  { char: "📣", keywords: "рупор анонс объявление" },
  { char: "📰", keywords: "газета новости пресса" },
  { char: "🗞", keywords: "газета новости пресса" },
  { char: "📌", keywords: "закрепить кнопка важное" },
  { char: "✅", keywords: "галочка готово да успех" },
  { char: "❌", keywords: "крест нет отмена ошибка" },
  { char: "⚠️", keywords: "предупреждение осторожно опасность" },
  { char: "ℹ️", keywords: "информация справка" },
  // City / infrastructure
  { char: "🏙", keywords: "город здания небоскребы" },
  { char: "🏗", keywords: "стройка кран строительство" },
  { char: "🏘", keywords: "дома район жилье" },
  { char: "🏛", keywords: "администрация власть суд банк" },
  { char: "🛣", keywords: "дорога трасса шоссе" },
  { char: "🚧", keywords: "ремонт дорога ограждение работы" },
  { char: "🌳", keywords: "дерево парк сквер зелень" },
  { char: "🏞", keywords: "парк природа пейзаж" },
  { char: "💡", keywords: "свет электричество идея лампа" },
  { char: "🚰", keywords: "вода водоснабжение" },
  { char: "🔌", keywords: "электричество розетка отключение" },
  // Transport
  { char: "🚗", keywords: "машина авто автомобиль" },
  { char: "🚕", keywords: "такси" },
  { char: "🚌", keywords: "автобус транспорт" },
  { char: "🚎", keywords: "троллейбус транспорт" },
  { char: "🚋", keywords: "трамвай транспорт" },
  { char: "🚇", keywords: "метро подземка" },
  { char: "🚆", keywords: "поезд электричка жд" },
  { char: "✈️", keywords: "самолет аэропорт рейс" },
  { char: "🚢", keywords: "корабль порт судно" },
  { char: "🚑", keywords: "скорая медицина авария" },
  { char: "🚒", keywords: "пожарная пожар" },
  { char: "🚓", keywords: "полиция милиция" },
  { char: "🚦", keywords: "светофор дорога" },
  { char: "🛴", keywords: "самокат кикшеринг" },
  { char: "🚲", keywords: "велосипед" },
  // Weather
  { char: "☀️", keywords: "солнце жара погода ясно" },
  { char: "🌤", keywords: "погода облака солнце" },
  { char: "☁️", keywords: "облака пасмурно погода" },
  { char: "🌧", keywords: "дождь погода ливень" },
  { char: "⛈", keywords: "гроза дождь шторм" },
  { char: "🌩", keywords: "гроза молния" },
  { char: "❄️", keywords: "снег холод зима мороз" },
  { char: "🌨", keywords: "снегопад зима погода" },
  { char: "🌫", keywords: "туман погода" },
  { char: "💨", keywords: "ветер шторм" },
  { char: "🌡", keywords: "температура градусник жара холод" },
  { char: "🌪", keywords: "смерч ураган шторм" },
  // People / society
  { char: "👮", keywords: "полицейский полиция" },
  { char: "👨‍⚕️", keywords: "врач медицина больница" },
  { char: "🧑‍🏫", keywords: "учитель школа образование" },
  { char: "👷", keywords: "рабочий стройка" },
  { char: "🧑‍🌾", keywords: "фермер сельское хозяйство урожай" },
  { char: "👶", keywords: "ребенок дети рождение" },
  { char: "👥", keywords: "люди население жители" },
  { char: "🎓", keywords: "выпускник образование университет школа" },
  { char: "🤝", keywords: "соглашение договор рукопожатие партнерство" },
  // Money / economy
  { char: "💰", keywords: "деньги бюджет финансы" },
  { char: "💵", keywords: "деньги доллар валюта" },
  { char: "💳", keywords: "карта оплата банк" },
  { char: "📈", keywords: "рост график вверх экономика" },
  { char: "📉", keywords: "падение график вниз кризис" },
  { char: "📊", keywords: "статистика график данные" },
  { char: "🏦", keywords: "банк финансы" },
  { char: "🛒", keywords: "покупки магазин торговля" },
  // Events / culture / sport
  { char: "🎉", keywords: "праздник событие поздравление" },
  { char: "🎊", keywords: "праздник конфетти" },
  { char: "🎂", keywords: "день рождения торт юбилей" },
  { char: "🎄", keywords: "новый год елка зима" },
  { char: "🎭", keywords: "театр культура спектакль" },
  { char: "🎬", keywords: "кино фильм съемки" },
  { char: "🎵", keywords: "музыка концерт" },
  { char: "🏆", keywords: "победа кубок трофей награда" },
  { char: "🥇", keywords: "золото первое место медаль" },
  { char: "⚽️", keywords: "футбол спорт мяч" },
  { char: "🏀", keywords: "баскетбол спорт" },
  { char: "🏐", keywords: "волейбол спорт" },
  { char: "🤾", keywords: "гандбол спорт" },
  { char: "🏊", keywords: "плавание спорт бассейн" },
  { char: "🥊", keywords: "бокс спорт единоборства" },
  // Misc
  { char: "🌍", keywords: "мир земля планета мировая" },
  { char: "🇷🇺", keywords: "россия флаг рф" },
  { char: "⭐️", keywords: "звезда рейтинг избранное" },
  { char: "💥", keywords: "взрыв удар авария" },
  { char: "🔍", keywords: "поиск расследование лупа" },
  { char: "📝", keywords: "запись документ заявление" },
  { char: "📅", keywords: "дата календарь расписание" },
  { char: "🕐", keywords: "время часы" },
  { char: "📍", keywords: "место геолокация точка адрес" },
  { char: "🏥", keywords: "больница медицина здоровье" },
  { char: "🏫", keywords: "школа образование" },
  { char: "🛍", keywords: "покупки шоппинг" },
  { char: "🍽", keywords: "еда ресторан кафе" },
  { char: "🐕", keywords: "собака животные" },
  { char: "🐈", keywords: "кот кошка животные" },
  { char: "🌊", keywords: "море вода волна пляж" },
  { char: "⛽️", keywords: "бензин топливо азс" },
  { char: "🗳", keywords: "выборы голосование урна" },
  { char: "⚖️", keywords: "суд право закон" },
  { char: "🚀", keywords: "запуск ракета старт космос" },
];

interface Props {
  /** Called with the chosen emoji character. */
  onPick: (emoji: string) => void;
  /** Optional trigger label; defaults to an icon-only button. */
  label?: string;
  title?: string;
  /** Extra classes for the trigger (e.g. to match a neighbouring input). */
  className?: string;
}

/** Button that opens a searchable emoji catalogue (Telegram-style). */
export function EmojiPickerButton({
  onPick,
  label,
  title = "Выбрать эмодзи",
  className = "",
}: Props) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");

  const results = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return EMOJI;
    return EMOJI.filter((e) => e.keywords.includes(q) || e.char === q);
  }, [query]);

  return (
    <>
      {label ? (
        <button
          type="button"
          className={`btn-outline ${className}`}
          title={title}
          onClick={() => setOpen(true)}
        >
          <Smile className="h-4 w-4" /> {label}
        </button>
      ) : (
        <button
          type="button"
          className={`btn-icon ${className}`}
          title={title}
          onClick={() => setOpen(true)}
        >
          <Smile className="h-4 w-4" />
        </button>
      )}

      {open && (
        <div
          className="fixed inset-0 z-[60] flex items-start justify-center bg-black/40 p-4"
          onMouseDown={(e) => {
            if (e.currentTarget === e.target) setOpen(false);
          }}
        >
          <div
            className="card my-16 w-full max-w-md p-4"
            onMouseDown={(e) => e.stopPropagation()}
          >
            <div className="mb-3 flex items-center justify-between">
              <h3 className="text-sm font-semibold">Выбор эмодзи</h3>
              <button className="btn-icon h-7 w-7" onClick={() => setOpen(false)}>
                <X className="h-4 w-4" />
              </button>
            </div>

            <div className="relative mb-3">
              <Search className="pointer-events-none absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
              <input
                autoFocus
                className="input pl-9"
                placeholder="Поиск: дождь, авария, футбол…"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
              />
            </div>

            <div className="grid max-h-72 grid-cols-8 gap-1 overflow-y-auto">
              {results.map((e) => (
                <button
                  key={e.char}
                  type="button"
                  title={e.keywords}
                  className="rounded-md p-1.5 text-xl transition-colors hover:bg-muted"
                  onClick={() => {
                    onPick(e.char);
                    setOpen(false);
                    setQuery("");
                  }}
                >
                  {e.char}
                </button>
              ))}
              {results.length === 0 && (
                <p className="col-span-8 py-6 text-center text-sm text-muted-foreground">
                  Ничего не найдено
                </p>
              )}
            </div>
          </div>
        </div>
      )}
    </>
  );
}
