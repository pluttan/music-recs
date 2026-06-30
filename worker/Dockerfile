FROM python:3.11-slim-bookworm

RUN apt-get update && apt-get install -y --no-install-recommends \
        libsndfile1 ffmpeg \
        libtag1v5 libyaml-0-2 libfftw3-double3 libavcodec59 libavformat59 libavutil57 libswresample4 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY analyzer.py .

CMD ["python", "-u", "analyzer.py", "--watch"]
