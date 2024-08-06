FROM python:3.11.9-alpine3.20

# cd /app
WORKDIR /app

# Copy files
COPY main.py .

# Install dependencies
RUN pip3 install fastapi[standard]

# Expose portfast
EXPOSE 8000

# Run FastAPI
CMD ["fastapi", "run", "main.py"]
