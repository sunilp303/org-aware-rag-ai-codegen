# 1. Submit a job and capture the job_id
RESPONSE=$(curl -s -X POST "$(terraform output -raw submit_endpoint)" \
  -H "x-api-key: $(terraform output -raw api_key)" \
  -H "Content-Type: application/json" \
  -d '{"comment":"Add error handling","code":"def test():\n    print(1)","file_path":"test.py","language":"python","repo":"test/repo"}')

echo "Submit Response:"
echo $RESPONSE | jq '.'

# 2. Extract job_id
JOB_ID=$(echo $RESPONSE | jq -r '.job_id')
echo "Job ID: $JOB_ID"

# 3. Poll status every 3 seconds
for i in {1..10}; do
  echo ""
  echo "Checking status (attempt $i)..."
  
  STATUS=$(curl -s "https://$REPLACE.execute-api.us-east-1.amazonaws.com/prod/status/$JOB_ID" \
    -H "x-api-key: $(terraform output -raw api_key)")
  
  echo $STATUS | jq '.'
  
  # Check if completed
  if echo $STATUS | jq -e '.status == "completed"' > /dev/null; then
    echo ""
    echo "✅ Job completed!"
    echo $STATUS | jq '.updated_code'
    break
  fi
  
  sleep 30
done
