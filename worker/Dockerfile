FROM pytorch/pytorch:2.5.1-cuda12.4-cudnn9-runtime
WORKDIR /worker
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
ENV PYTHONUNBUFFERED=1 HF_HOME=/runpod-volume/huggingface
CMD ["python", "handler.py"]
