#!/bin/bash

ENV=${1:-development}

echo "Setting up environment: $ENV"

case $ENV in
  "production")
    if [ -f .prod.env ]; then
      export $(cat .prod.env | grep -v '^#' | xargs)
      echo "Production environment variables loaded"
    else
      echo "Error: .prod.env file not found"
      exit 1
    fi
    ;;
  "development")
        if [ -f .dev.env ]; then
      export $(cat .dev.env | grep -v '^#' | xargs)
      echo "Development environment variables loaded"
    else
      echo "Error: .dev.env file not found"
      exit 1
    fi
    ;;
  "local")
    if [ -f .local.env ]; then
      export $(cat .local.env | grep -v '^#' | xargs)
      echo "Local environment variables loaded"
    else
      echo "Error: .local.env file not found"
      exit 1
    fi
    ;;
  *)
    echo "Invalid environment. Use: production, development, or local"
    exit 1
    ;;
esac