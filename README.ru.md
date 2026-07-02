![Header](header.png)

<div align="center">

# music-recs

**Самостоятельно размещаемые аудио-рекомендации музыки на основе MusiCNN-эмбеддингов**

[![License](https://img.shields.io/badge/license-MIT-2C2C2C?style=for-the-badge&labelColor=1E1E1E)](LICENSE)
[![Python](https://img.shields.io/badge/Python-worker-2C2C2C?style=for-the-badge&logo=python&labelColor=1E1E1E)]()
[![FastAPI](https://img.shields.io/badge/FastAPI-api-2C2C2C?style=for-the-badge&logo=fastapi&labelColor=1E1E1E)]()
[![pgvector](https://img.shields.io/badge/pgvector-PostgreSQL_16-2C2C2C?style=for-the-badge&logo=postgresql&labelColor=1E1E1E)]()
[![Docker](https://img.shields.io/badge/Docker-compose-2C2C2C?style=for-the-badge&logo=docker&labelColor=1E1E1E)]()

</div>

Самостоятельно размещаемый пайплайн музыкальных рекомендаций, работающий рядом с библиотекой Navidrome. Извлекает реальные аудио-признаки (BPM, тональность, громкость, энергия, танцевальность, настроение) и 200-мерные MusiCNN-эмбеддинги из каждого трека, хранит их в pgvector и предоставляет эндпоинты similarity/radio/mood. Systemd-таймеры выгружают `.m3u`-плейлисты в директорию библиотеки Navidrome, так что любой Subsonic-клиент видит их как обычные плейлисты.

## ■ Возможности

- ❖ **Audio-based similarity** — косинусное KNN по 200-мерным MusiCNN-эмбеддингам, не по метаданным
- ❖ **Feature extraction** — BPM, тональность, громкость, энергия, танцевальность, настроение через essentia-tensorflow
- ❖ **pgvector search** — ivfflat cosine-индекс для быстрых запросов схожести
- ❖ **REST API** — эндпоинты `/similar`, `/radio`, `/mood/<mood>`, `/stats` через FastAPI
- ❖ **m3u playlist export** — systemd-таймеры записывают `.m3u`-файлы mood/daily-mix в директорию библиотеки Navidrome
- ❖ **Auto-scan worker** — почасовое инкрементальное сканирование, пропускает треки с неизменившимися size/mtime
- ❖ **Docker Compose** — одна команда `make up` поднимает PostgreSQL 16 + pgvector + worker + API

## ■ Стек

<div align="center">

| Компонент | Технология |
|-----------|------------|
| Извлечение признаков | essentia-tensorflow + MusiCNN |
| Метаданные | mutagen |
| Vector DB | PostgreSQL 16 + pgvector (ivfflat) |
| API | FastAPI + uvicorn |
| Worker | Python (analyzer.py, watch mode) |
| Плейлисты | m3u dumper (systemd timer) |
| Деплой | Docker Compose |

</div>

## ■ Как работает

```
/data/music/library/  (shared volume, read-only for worker)
        |
[worker] scans -> extracts features + embedding -> INSERT tracks
        |
   [recs-db (pgvector)]
        |
[api] /similar?path=X&n=20 -> vector KNN
        |
[m3u dumper, systemd timer] -> writes _playlists/*.m3u
        |
   Navidrome auto-scans -> clients see playlists
```

## ■ Запуск

```bash
# Скачать модели essentia
make install

# Запустить все сервисы
make up

# Принудительное полное повторное сканирование библиотеки
make analyze

# Посмотреть статистику
make stats

# Остановить
make down
```

Путь к библиотеке по умолчанию — `/data/music/library/`; переопределяется через переменную окружения `LIBRARY_PATH`.

## ■ License

MIT © [pluttan](https://github.com/pluttan)
