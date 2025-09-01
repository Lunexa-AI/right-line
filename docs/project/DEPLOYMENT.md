# Gweta API Deployment Guide

This document provides instructions for deploying the Gweta backend API to Render and configuring the frontend on Vercel.

## Backend Deployment (Render)

The backend is a FastAPI application packaged with Poetry. We recommend deploying it as a Web Service on Render.

### 1. Create a New Web Service

- Log in to your Render account.
- Click **New +** > **Web Service**.
- Connect your GitHub account and select the `right-line` repository.

### 2. Configure the Service

- **Name:** `gweta-api` (or a name of your choice).
- **Region:** Choose a region closest to your users (e.g., Frankfurt).
- **Branch:** `main`.
- **Root Directory:** Leave this blank (as `pyproject.toml` is in the root).
- **Runtime:** `Python 3`.
- **Build Command:** `poetry install --no-dev --no-interaction --no-ansi`.
- **Start Command:** `gunicorn -w 4 -k uvicorn.workers.UvicornWorker api.main:app --bind 0.0.0.0:$PORT`.
- **Instance Type:** `Starter` is sufficient for development and testing. Choose a larger instance for production based on traffic.

### 3. Set Python Version

- Go to the **Environment** tab for your new service.
- Add an Environment Variable:
  - **Key:** `PYTHON_VERSION`
  - **Value:** `3.11`

### 4. Add Environment Variables

- In the same **Environment** tab, add the following environment variables. You'll need to create a group for secrets or add them individually.
- These should be based on your local `.env` file or cloud configuration.

```sh
# Example Environment Variables
# Add all required variables for your application to run
GOOGLE_APPLICATION_CREDENTIALS_JSON='{"type": "service_account", ...}'
OPENAI_API_KEY="sk-..."
MILVUS_URI="your-milvus-uri"
MILVUS_TOKEN="your-milvus-token"
# Add any other variables your settings require
```

### 5. Deploy

- Click **Create Web Service**.
- Render will automatically build and deploy your application. You can monitor the progress in the **Events** tab.
- Once deployed, your API will be available at the URL provided by Render (e.g., `https://gweta-api.onrender.com`).

### 6. Auto-Deploy (Optional)

- In your service settings, you can enable **Auto-Deploy** to automatically redeploy the application whenever you push changes to the configured branch (`main`).

---

## Frontend Deployment (Vercel)

The frontend is a separate service and should be deployed on Vercel as a static site or Jamstack application.

### Configuration

- In your frontend's code, make sure to update the API endpoint to point to your new Render backend URL.
- This is typically stored in an environment variable, for example: `NEXT_PUBLIC_API_URL=https://gweta-api.onrender.com`.

By keeping the backend and frontend deployments separate, you can manage and scale them independently.
