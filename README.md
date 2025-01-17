# Jira Tempo Worklog Tool

A Python-based tool for automating Jira Tempo worklog entries using Selenium and aiohttp.

## Features

- Automated cookie-based authentication
- Async HTTP requests for better performance
- Headless browser operation
- Persistent credential storage

## Requirements

- Python 3.7+
- Chrome browser
- ChromeDriver

## Installation

1. Clone the repository
2. Install dependencies:
```bash
pip install selenium aiohttp
```

## Configuration

Create a `CredentialSettings.json` file in the root directory:

```json
{
    "user": "your_jira_username",
    "pwd": "your_jira_password"
}
```

## Usage

You can first use the Fiddler program to observe what POST request is sent to JIRA during a Tempo log recording. From this, you can see where and what JSON needs to be sent.

![image](https://github.com/user-attachments/assets/b12f26f0-35c2-4442-8060-fd6a77aac7a3)

```python
from tempo import CookieService, CredentialSettings

async def main():
    cookie_service = CookieService(CredentialSettings())
    
    # Get authentication cookies
    await cookie_service.get_jira_cookies()
    
    # Example worklog data
    tempo_data = {
        "worker": "JIRAUSER15",
        "started": "2025-01-22",
        "timeSpentSeconds": 3600,
        "originTaskId": "42"
    }
    
    # Post worklog
    await cookie_service.post_tempo_worklog(tempo_data)

asyncio.run(main())
```

## Error Handling

The tool includes comprehensive error handling and logging. Check the console output for detailed information about any issues that occur during execution.

## Security Note

- Credentials are stored locally in `CredentialSettings.json`
- Use environment variables for sensitive information in production
