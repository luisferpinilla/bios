FROM python:3.11.9-alpine3.20

# cd /app
WORKDIR /app

# Copy files
COPY main.py requirements.txt ./

# Install dependencies
RUN pip3 install -r requirements.txt

# Expose portfast
EXPOSE 8000

# Run FastAPI
CMD ["fastapi", "run", "main.py"]
