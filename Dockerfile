FROM python:3.9-slim

# Install System Dependencies
RUN apt-get update && apt-get install -y \
    ffmpeg \
    mpv \
    git \
    alsa-utils \
    libasound2 \
    procps \
    socat \
    && rm -rf /var/lib/apt/lists/*

# Set Working Directory
WORKDIR /app

# Install Python Libraries
RUN pip install --no-cache-dir \
    flask \
    pyserial \
    yt-dlp \
    ytmusicapi \
    requests \
    mutagen \
    esptool

# Copy semua file
COPY . /app

# Permission script
RUN chmod +x /app/play.sh

# Environment Variable
ENV PYTHONUNBUFFERED=1

# Command start
CMD ["python", "app.py"]
