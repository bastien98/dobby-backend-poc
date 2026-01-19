# Dobby Backend POC

A FastAPI backend for the Dobby POC, deployable to AWS App Runner.

## 🚀 Deployment Commands (Copy & Paste)

These commands use your specific AWS Account ID (`116739015003`) and Region (`eu-west-1`).

### 1. Login to AWS ECR
```bash
aws ecr get-login-password --region eu-west-1 | docker login --username AWS --password-stdin 116739015003.dkr.ecr.eu-west-1.amazonaws.com
```

### 2. Build & Push Image
**Note:** The `--platform linux/amd64` flag is critical for AWS App Runner compatibility if building on a Mac (Apple Silicon).

```bash
# Build/TAG/Push
docker build --platform linux/amd64 -t dobby-backend .
docker tag dobby-backend:latest 116739015003.dkr.ecr.eu-west-1.amazonaws.com/dobby-backend:latest
docker push 116739015003.dkr.ecr.eu-west-1.amazonaws.com/dobby-backend:latest
```

### 3. Deploy
Go to the AWS App Runner console and deploy the new image.

---


## 🧪 Testing

**Local:**
```bash
poetry run python -m uvicorn main:app --port 8000 --reload
```

**Upload Test:**
```bash
curl -F "file=@test.pdf" https://3edaeenmik.eu-west-1.awsapprunner.com/upload
```
