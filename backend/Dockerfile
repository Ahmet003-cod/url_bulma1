# Playwright için hazırlanmış resmi Python imajını kullanıyoruz
FROM mcr.microsoft.com/playwright/python:v1.40.0-jammy

# Çalışma dizinini ayarla
WORKDIR /app

# Gerekli sistem paketlerini güncelle
RUN apt-get update && apt-get install -y \
    libnss3 \
    libnspr4 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libxkbcommon0 \
    libxcomposite1 \
    libxdamage1 \
    libxext6 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libasound2 \
    libpango-1.0-0 \
    libcairo2 \
    && rm -rf /var/lib/apt/lists/*

# Gereksinimleri kopyala ve yükle
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Playwright tarayıcılarını yükle (Chromium yeterli)
RUN playwright install chromium

# Tüm backend dosyalarını kopyala
COPY . .

# Render'ın verdiği portu kullan
ENV PORT=8000

# Uygulamayı başlat
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT}"]
