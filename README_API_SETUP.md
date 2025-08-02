# Kimi API Setup Instructions

## Current Status
❌ **API Key Issue Detected**: Your current API key appears to be invalid or expired.

## How to Fix

### 1. Get a Valid API Key
1. Visit [Moonshot AI](https://platform.moonshot.cn/)
2. Sign up for an account
3. Navigate to API Keys section
4. Generate a new API key
5. Copy the key (it should start with `sk-`)

### 2. Update Your .env File
Replace the API key in your `.env` file:

```bash
# Edit .env file
nano .env

# Update this line:
KIMI_API_KEY=your_new_valid_api_key_here
```

### 3. Test Your Setup

Run the API test script:
```bash
python3 test_api_key.py
```

You should see:
```
✅ API key is valid!
```

### 4. Run Integration Tests
Once your API key is valid, run the integration tests:

```bash
python3 -m pytest tests/test_kimi_api_integration.py -v -s
```

## API Key Format
- Should start with `sk-`
- Typically 40-60 characters long
- Example: `sk-1234567890abcdef1234567890abcdef12345678`

## Troubleshooting

### If tests still fail:
1. Check your internet connection
2. Verify the API key is correctly copied
3. Ensure no extra spaces or quotes in the .env file
4. Check if the API key has usage limits or is expired

### Environment Variables
The following variables are used:
- `KIMI_API_KEY`: Your Moonshot API key
- `KIMI_BASE_URL`: API endpoint (default: https://api.moonshot.cn/v1)

### Manual Testing
You can also test manually with curl:
```bash
curl -X POST "https://api.moonshot.cn/v1/chat/completions" \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "kimi-k2-0711-preview",
    "messages": [{"role": "user", "content": "Hello"}]
  }'
```