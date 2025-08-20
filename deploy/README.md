# DEPRECATED: Deployment Configuration

⚠️ **This directory is deprecated in favor of Vercel serverless deployment.**

The Docker-based deployment approach has been replaced with:
- **Vercel Functions** for serverless API deployment
- **Milvus Cloud** for vector storage
- **OpenAI API** for AI capabilities

## 🚀 New Deployment Approach

See the updated deployment documentation:
- [**Deployment Guide**](../docs/DEPLOYMENT.md) - Vercel deployment instructions
- [**Quick Start**](../docs/QUICKSTART.md) - Get running in 5 minutes
- [**MVP Architecture**](../docs/project/MVP_ARCHITECTURE.md) - Serverless architecture

## 📦 Migration

To migrate from Docker to Vercel:
1. Set up Vercel account and CLI
2. Configure OpenAI API key
3. Set up Milvus Cloud cluster
4. Deploy with `vercel --prod`

See [MIGRATION_NOTES.md](../MIGRATION_NOTES.md) for detailed migration steps.

---

*This directory is kept for reference only. Use Vercel deployment for new installations.*
