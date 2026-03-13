# Data Vacuum Deployment Guide

This guide will walk you through deploying the Data Vacuum web dashboard to AWS using Docker.

## 1. Pushing to GitHub

First, you need to push your local repository to a remote GitHub repository.

1. Go to [GitHub](https://github.com/) and create a new, empty repository.
2. Link your local project to GitHub and push your code:
   ```bash
   git branch -M main
   git remote add origin https://github.com/YOUR_USERNAME/YOUR_REPO_NAME.git
   git push -u origin main
   ```

## 2. Docker Deployment on AWS (App Runner)

AWS App Runner is the easiest, most elegant way to deploy a containerized web service like Data Vacuum directly from your GitHub repository.

1. Sign in to the [AWS Management Console](https://aws.amazon.com/console/) and search for **App Runner**.
2. Click **Create an App Runner service**.
3. Under **Source**, choose **Source code repository**.
4. Connect your GitHub account and select your `data-vacuum` repository and the `main` branch.
5. Under **Deployment settings**, choose **Automatic**. This means every time you push to GitHub, AWS will automatically rebuild and deploy the new version.
6. Under **Build settings**, choose **Use a configuration file** if you want to use the Dockerfile, or configure it via the UI:
   - **Build command:** `pip install -r requirements.txt && playwright install chromium --with-deps`
   - **Start command:** `uvicorn app:app --host 0.0.0.0 --port 8000`
   - **Port:** `8000`
7. Under **Environment variables**, carefully add your API keys. **Do not put these in your code.**
   - `GROQ_API_KEY`: `your_key_here`
   - `TAVILY_API_KEY`: `your_key_here`
8. Keep the default instance size (at least 2 vCPU and 4GB memory is recommended for running Playwright browsers and ONNX models).
9. Click **Create & deploy**.

AWS will handle building the Docker container, provisioning the infrastructure, and assigning you a live HTTPS URL.

## Alternative: AWS EC2 (Manual Deployment)

If you prefer to run it manually on a server (cheaper but requires more setup):

1. Launch an **Ubuntu EC2 Instance** (at least `t3.medium`).
2. SSH into your instance.
3. Install Docker:
   ```bash
   sudo apt update
   sudo apt install docker.io -y
   ```
4. Clone your repository:
   ```bash
   git clone https://github.com/YOUR_USERNAME/YOUR_REPO_NAME.git
   cd YOUR_REPO_NAME
   ```
5. Create a `.env` file on the server with your keys:
   ```bash
   nano .env
   # Add GROQ_API_KEY=... and TAVILY_API_KEY=...
   ```
6. Build and run the Docker container:
   ```bash
   sudo docker build -t data-vacuum .
   sudo docker run -d -p 80:8000 --env-file .env data-vacuum
   ```
7. Your app will now be live on your EC2 instance's public IP address!
