ENVIRONMENT=${1:-development}

echo "🚀 Starting deployment to $ENVIRONMENT environment..."

# AWS 자격 증명 확인
if ! aws sts get-caller-identity > /dev/null 2>&1; then
    echo "❌ AWS credentials not configured. Please run 'aws configure'"
    exit 1
fi

# EB CLI 설치 확인
if ! command -v eb &> /dev/null; then
    echo "📦 Installing EB CLI..."
    pip install awsebcli
fi

# 환경별 배포
case $ENVIRONMENT in
  "prod")
    echo "📦 Deploying to Production..."
    eb use prod-3
    eb deploy prod-3
    ;;
    
  "dev")
    echo "📦 Deploying to Development..."
    eb use develop-2
    eb deploy develop-2
    ;;

  *)
    echo "❌ Invalid environment. Use: prod, dev"
    exit 1
    ;;
esac

if [ $? -eq 0 ]; then
    echo "✅ Deployment completed successfully for $ENVIRONMENT environment!"
    
    # 배포 후 상태 확인
    echo "📊 Checking application health..."
    eb health
    
    # URL 표시
    echo "🌐 Application URL:"
    eb status | grep "CNAME"
    
    # 환경변수 확인 (참고용)
    echo ""
    echo "🔧 Current environment variables:"
    eb printenv
else
    echo "❌ Deployment failed!"
    exit 1
fi