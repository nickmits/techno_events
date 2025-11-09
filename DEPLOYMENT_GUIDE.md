# Deployment Guide for TechnoMate

This guide covers deploying your TechnoMate application to production using the recommended split deployment strategy.

---

## 🎯 Recommended Deployment Architecture

```
Frontend (React + Vite) → Vercel (Free)
Backend (FastAPI + LangGraph) → Render/Railway (Free tier available)
```

**Why this approach?**
- Vercel excels at static/frontend hosting with global CDN
- Render/Railway support long-running Python processes with persistent storage
- No timeout limitations on backend
- Better performance and cost-effectiveness

---

## 📦 Part 1: Deploy Backend to Render

### Prerequisites
1. Create a free account at [Render.com](https://render.com)
2. Push your code to GitHub if you haven't already

### Step-by-Step Backend Deployment

#### 1. Create `render.yaml` configuration

Already created at the root of your project. This file tells Render how to deploy your backend.

#### 2. Create `requirements.txt` (if not exists)

```bash
cd backend
pip freeze > requirements.txt
```

#### 3. Update backend for production

Make sure your `backend/main.py` has proper CORS settings for your Vercel frontend:

```python
# In backend/main.py, update CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",  # Local development
        "https://your-app-name.vercel.app",  # Your Vercel URL (update after deploying frontend)
        "https://*.vercel.app",  # All Vercel preview deployments
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

#### 4. Deploy to Render

**Option A: From Dashboard (Easiest)**

1. Go to [Render Dashboard](https://dashboard.render.com)
2. Click "New +" → "Web Service"
3. Connect your GitHub repository
4. Select the `techno_events` repository
5. Configure:
   - **Name**: `technomate-backend`
   - **Region**: Frankfurt (closest to Athens)
   - **Branch**: `main`
   - **Root Directory**: Leave blank (render.yaml handles this)
   - **Runtime**: Python 3
   - **Build Command**: `cd backend && pip install -r requirements.txt`
   - **Start Command**: `cd backend && uvicorn main:app --host 0.0.0.0 --port $PORT`
   - **Instance Type**: Free

6. **Environment Variables** - Add these in Render dashboard:
   ```
   OPENAI_API_KEY=your_openai_api_key_here
   COHERE_API_KEY=your_cohere_api_key_here (optional)
   TAVILY_API_KEY=your_tavily_api_key_here
   PYTHON_VERSION=3.11
   ```

7. Click "Create Web Service"

8. Wait 5-10 minutes for deployment

9. Your backend will be available at: `https://technomate-backend.onrender.com`

**Option B: Using render.yaml (Automated)**

1. Make sure `render.yaml` is at the root of your repo
2. Push to GitHub
3. In Render dashboard, click "New +" → "Blueprint"
4. Connect your repo and select `render.yaml`
5. Set environment variables
6. Deploy

#### 5. Test your backend

```bash
curl https://technomate-backend.onrender.com/
# Should return: {"status":"online","service":"Techno Events API","version":"1.0.0"}

curl https://technomate-backend.onrender.com/api/health
# Should return health check data
```

---

## 🎨 Part 2: Deploy Frontend to Vercel

### Prerequisites
1. Create a free account at [Vercel.com](https://vercel.com)
2. Install Vercel CLI (optional): `npm i -g vercel`

### Step-by-Step Frontend Deployment

#### 1. Update `.gitignore` in frontend

Make sure these are in `frontend/.gitignore`:
```
.env.local
.env*.local
dist
node_modules
```

#### 2. Deploy to Vercel

**Option A: From Dashboard (Easiest)**

1. Go to [Vercel Dashboard](https://vercel.com/dashboard)
2. Click "Add New..." → "Project"
3. Import your GitHub repository
4. Configure project:
   - **Framework Preset**: Vite
   - **Root Directory**: `frontend`
   - **Build Command**: `npm run build`
   - **Output Directory**: `dist`
   - **Install Command**: `npm install`

5. **Environment Variables** - Add in Vercel dashboard:
   ```
   VITE_API_URL=https://technomate-backend.onrender.com
   ```

6. Click "Deploy"

7. Wait 2-3 minutes for deployment

8. Your frontend will be available at: `https://your-project-name.vercel.app`

**Option B: Using Vercel CLI**

```bash
cd frontend

# Login to Vercel
vercel login

# Deploy
vercel

# Follow the prompts:
# Set up and deploy? Yes
# Which scope? [Your account]
# Link to existing project? No
# Project name? technomate
# In which directory is your code located? ./
# Want to modify settings? Yes
#   - Build Command: npm run build
#   - Output Directory: dist
#   - Development Command: npm run dev

# Set environment variable
vercel env add VITE_API_URL production
# Enter: https://technomate-backend.onrender.com

# Deploy to production
vercel --prod
```

#### 3. Update backend CORS settings

Now that you have your Vercel URL, go back to your backend code and update CORS:

```python
# backend/main.py
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "https://your-actual-vercel-url.vercel.app",  # Update with your real URL
        "https://*.vercel.app",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

Commit and push to trigger redeployment on Render.

---

## 🔧 Part 3: Configuration Files

### Backend: `render.yaml`

```yaml
services:
  - type: web
    name: technomate-backend
    runtime: python
    plan: free
    buildCommand: "cd backend && pip install -r requirements.txt"
    startCommand: "cd backend && uvicorn main:app --host 0.0.0.0 --port $PORT"
    envVars:
      - key: PYTHON_VERSION
        value: 3.11
      - key: OPENAI_API_KEY
        sync: false  # Set manually in dashboard for security
      - key: COHERE_API_KEY
        sync: false
      - key: TAVILY_API_KEY
        sync: false
```

### Frontend: `vercel.json`

Already created at `frontend/vercel.json`:

```json
{
  "buildCommand": "npm run build",
  "outputDirectory": "dist",
  "framework": "vite",
  "rewrites": [
    {
      "source": "/(.*)",
      "destination": "/index.html"
    }
  ]
}
```

---

## 📊 Post-Deployment Checklist

### Backend (Render)
- [ ] Service is running (green status)
- [ ] Environment variables are set
- [ ] Health check endpoint works: `https://your-backend.onrender.com/api/health`
- [ ] CORS is configured correctly
- [ ] Logs show no errors

### Frontend (Vercel)
- [ ] Deployment successful (green checkmark)
- [ ] Environment variable `VITE_API_URL` is set
- [ ] Site loads at your Vercel URL
- [ ] Can send test query and get response from backend
- [ ] No CORS errors in browser console
- [ ] Custom domain configured (optional)

### Testing
- [ ] Test a query: "What events are happening this weekend?"
- [ ] Verify human-in-the-loop works (location request)
- [ ] Check event display with distance sorting
- [ ] Test follow-up queries
- [ ] Verify caching works (second query is faster)

---

## 🚨 Common Issues & Solutions

### Issue 1: CORS Errors

**Error**: `Access to XMLHttpRequest has been blocked by CORS policy`

**Solution**:
1. Update `allow_origins` in `backend/main.py` with your Vercel URL
2. Redeploy backend
3. Clear browser cache

### Issue 2: Backend Cold Starts

**Problem**: First request after 15 min of inactivity is slow (30+ seconds)

**Why**: Render free tier spins down after inactivity

**Solutions**:
- Upgrade to paid Render plan ($7/month, no cold starts)
- Use a cron job to ping your backend every 14 minutes: https://cron-job.org
- Accept the limitation for MVP

### Issue 3: Environment Variables Not Working

**Error**: `OPENAI_API_KEY not found`

**Solution**:
1. Verify env vars are set in Render dashboard
2. Redeploy the service
3. Check logs: `https://dashboard.render.com/web/your-service/logs`

### Issue 4: Build Failures

**Frontend build fails**:
```bash
# Check build locally first
cd frontend
npm run build
```

**Backend build fails**:
```bash
# Check dependencies
cd backend
pip install -r requirements.txt
python -m uvicorn main:app
```

### Issue 5: File Storage (CSV/Embedding Cache)

**Problem**: CSV file changes are lost on Render free tier

**Solution** (for production):
- Use Render's persistent disk (paid feature, $1/GB/month)
- OR migrate to PostgreSQL + external vector DB (Pinecone/Weaviate)
- For MVP: Accept that cache rebuilds on each deployment

---

## 💰 Cost Breakdown

### Free Tier (Your Current Setup)
- **Vercel**: Free (Hobby plan)
  - 100 GB bandwidth/month
  - Unlimited deployments
  - Preview deployments for PRs

- **Render**: Free
  - 750 hours/month (enough for 1 service)
  - 512 MB RAM
  - Spins down after 15 min inactivity
  - No persistent disk

- **OpenAI API**: Pay-per-use
  - ~$0.02 per query (without cache)
  - ~$0.002 per query (with cache)
  - Estimated: $5-10/month for moderate use

**Total**: $5-10/month (just API costs)

### Paid Tier (For Production)
- **Vercel Pro**: $20/month
  - More bandwidth
  - Better performance

- **Render Starter**: $7/month
  - No cold starts
  - 512 MB persistent disk ($1/month extra)

- **OpenAI API**: ~$10-50/month depending on usage

**Total**: $38-78/month

---

## 🔄 CI/CD Auto-Deployment

Both Vercel and Render support automatic deployments from GitHub:

### Setup Auto-Deploy

1. **Vercel** (already configured):
   - Automatically deploys on push to `main`
   - Creates preview deployments for PRs

2. **Render**:
   - Go to your service settings
   - Enable "Auto-Deploy: Yes"
   - Now pushes to `main` trigger redeployment

### Workflow
```
git add .
git commit -m "Update feature"
git push origin main
↓
GitHub triggers webhooks
↓
Vercel rebuilds frontend (2-3 min)
Render rebuilds backend (5-10 min)
↓
Your site is live with latest changes!
```

---

## 🎯 Alternative Deployment Options

### Option 1: Railway (Alternative to Render)

**Pros**:
- $5 free credit/month
- Better cold start performance
- Easier configuration

**Cons**:
- Free tier more limited than Render

**Deploy**:
1. Go to [Railway.app](https://railway.app)
2. "New Project" → "Deploy from GitHub"
3. Select your repo
4. Railway auto-detects Python and sets up
5. Add environment variables
6. Deploy

### Option 2: Fly.io (Advanced)

**Pros**:
- Great performance
- Edge deployment
- Generous free tier

**Cons**:
- Requires Dockerfile
- Steeper learning curve

### Option 3: Full Vercel (Requires Refactoring)

**Changes needed**:
1. Convert FastAPI routes to Vercel serverless functions
2. Replace CSV with Supabase/PostgreSQL
3. Replace Qdrant with Pinecone
4. Optimize LangGraph for <60 second execution

**Not recommended** for your current architecture.

---

## 📝 Environment Variables Reference

### Backend (Render/Railway)
```bash
OPENAI_API_KEY=sk-...
COHERE_API_KEY=... (optional)
TAVILY_API_KEY=tvly-...
PYTHON_VERSION=3.11
```

### Frontend (Vercel)
```bash
VITE_API_URL=https://your-backend.onrender.com
```

---

## 🚀 Quick Start (TL;DR)

```bash
# 1. Deploy Backend to Render
# - Go to render.com → New Web Service
# - Connect GitHub repo
# - Set root directory: backend
# - Add environment variables
# - Deploy

# 2. Deploy Frontend to Vercel
cd frontend
vercel
# Follow prompts, set VITE_API_URL

# 3. Update CORS in backend with Vercel URL
# 4. Test your live site!
```

---

## 🆘 Need Help?

- **Render Docs**: https://render.com/docs
- **Vercel Docs**: https://vercel.com/docs
- **Railway Docs**: https://docs.railway.app

**Common Questions**:

**Q: Can I deploy the whole thing to Vercel?**
A: Not recommended. Vercel serverless has 10-60 second timeout limits. Your backend needs longer.

**Q: What about Heroku?**
A: Heroku removed free tier. Render/Railway are better alternatives.

**Q: How do I add a custom domain?**
A: Both Vercel and Render support custom domains in their dashboards. Just add your domain and update DNS records.

**Q: Will my CSV data persist?**
A: On Render free tier, no. On paid tier with persistent disk, yes. For production, consider migrating to PostgreSQL.

---

## 🎉 Success!

Once deployed, your app will be live at:
- **Frontend**: `https://your-app.vercel.app`
- **Backend**: `https://your-backend.onrender.com`

Share it with the Athens techno community and start collecting feedback!

---

**Good luck with your deployment! 🚀**
