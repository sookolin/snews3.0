"use client";

import { useEffect, useRef } from "react";

interface Props {
  latitude?: number | null;
  longitude?: number | null;
  onPick: (lat: number, lon: number, address?: string) => void;
}

declare global {
  interface Window {
    ymaps?: any;
  }
}

let scriptPromise: Promise<void> | null = null;

function loadYmaps(apiKey: string): Promise<void> {
  if (typeof window === "undefined") return Promise.reject();
  if (window.ymaps) return Promise.resolve();
  if (scriptPromise) return scriptPromise;
  scriptPromise = new Promise<void>((resolve, reject) => {
    const s = document.createElement("script");
    const key = apiKey ? `&apikey=${apiKey}` : "";
    s.src = `https://api-maps.yandex.ru/2.1/?lang=ru_RU${key}`;
    s.onload = () => window.ymaps.ready(() => resolve());
    s.onerror = () => reject(new Error("Yandex Maps failed to load"));
    document.head.appendChild(s);
  });
  return scriptPromise;
}

/** Interactive Yandex map to pick a geolocation. Click to set a point. */
export function YandexMapPicker({ latitude, longitude, onPick }: Props) {
  const ref = useRef<HTMLDivElement>(null);
  const mapRef = useRef<any>(null);
  const placemarkRef = useRef<any>(null);

  useEffect(() => {
    const apiKey = process.env.NEXT_PUBLIC_YANDEX_MAPS_KEY || "";
    let disposed = false;

    loadYmaps(apiKey)
      .then(() => {
        if (disposed || !ref.current) return;
        const center = [latitude ?? 55.751244, longitude ?? 37.618423];
        const map = new window.ymaps.Map(ref.current, {
          center,
          zoom: latitude ? 15 : 10,
          controls: ["zoomControl", "searchControl"],
        });
        mapRef.current = map;

        const setPoint = (coords: number[]) => {
          if (placemarkRef.current) {
            placemarkRef.current.geometry.setCoordinates(coords);
          } else {
            placemarkRef.current = new window.ymaps.Placemark(coords, {}, { draggable: true });
            map.geoObjects.add(placemarkRef.current);
            placemarkRef.current.events.add("dragend", () => {
              const c = placemarkRef.current.geometry.getCoordinates();
              resolveAddress(c);
            });
          }
        };

        const resolveAddress = (coords: number[]) => {
          window.ymaps.geocode(coords).then((res: any) => {
            const obj = res.geoObjects.get(0);
            const address = obj ? obj.getAddressLine() : undefined;
            onPick(coords[0], coords[1], address);
          }).catch(() => onPick(coords[0], coords[1]));
        };

        if (latitude && longitude) setPoint([latitude, longitude]);

        map.events.add("click", (e: any) => {
          const coords = e.get("coords");
          setPoint(coords);
          resolveAddress(coords);
        });
      })
      .catch(() => {
        if (ref.current) {
          ref.current.innerHTML =
            '<div style="padding:1rem;font-size:13px;color:#888">Не удалось загрузить Яндекс.Карты. Укажите координаты вручную ниже.</div>';
        }
      });

    return () => {
      disposed = true;
      if (mapRef.current) {
        mapRef.current.destroy();
        mapRef.current = null;
        placemarkRef.current = null;
      }
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return <div ref={ref} className="h-64 w-full overflow-hidden rounded-md border border-border" />;
}
