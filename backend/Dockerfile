# backend/Dockerfile

# Use an official Python runtime as a parent image
FROM python:3.12-slim-bookworm

# Set the working directory in the container
WORKDIR /app

# Install any needed packages specified in requirements.txt
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code
COPY . .

# Create data directory if it doesn't exist
RUN mkdir -p /app/data

# Expose the port the app runs on (no longer strictly needed for backend-only, but good practice)
EXPOSE 8000

# Run the application as a Python script
CMD ["python", "main.py"]