# Recipe for building CleanSet into a container that Cloud Run can run.
FROM python:3.12-slim
WORKDIR /srv
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app
# the demo deal shown by the "Try the demo deal" button
COPY data/demo/planted ./data/demo/planted
ENV PORT=8080
CMD exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT}
