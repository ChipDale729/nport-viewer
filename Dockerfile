FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
ENV SEC_USER_AGENT="NPORT Viewer (caleb.mok@hotmail.com)"
EXPOSE 3000
CMD ["gunicorn", "app:app", "--bind", "0.0.0.0:3000"]
