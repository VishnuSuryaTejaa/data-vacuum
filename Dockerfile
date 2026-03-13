FROM python:3.11-slim

# Install system dependencies required for Playwright and other tools
RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    libnss3 \
    libatk-bridge2.0-0 \
    libxcomposite1 \
    libxrandr2 \
    libx11-xcb1 \
    libxcb-dri3-0 \
    libxss1 \
    libasound2 \
    fonts-liberation \
    libappindicator3-1 \
    libxdamage1 \
    libgbm1 \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# HF Spaces sandboxes the app dir as read-only; write everything to /tmp
ENV HOME=/tmp
ENV HF_HOME=/tmp/hf_cache

# Limit CPU parallelism to the 2 vCPUs available on free HF Space tier
# Without these, PyTorch/OpenMP/MKL spawn ~32 threads and thrash the CPU
ENV OMP_NUM_THREADS=2
ENV MKL_NUM_THREADS=2
ENV TOKENIZERS_PARALLELISM=false
ENV NUMEXPR_NUM_THREADS=2

# Copy requirements first to leverage Docker cache
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright browsers (Chromium only to save space)
RUN playwright install chromium
RUN playwright install-deps chromium

# Copy the rest of the application
COPY . .

# Create writable output dir in /tmp at runtime
RUN mkdir -p /tmp/output

# HF Spaces uses port 7860
EXPOSE 7860

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "7860"]
