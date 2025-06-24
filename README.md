# GitHub Assistant Bot

A Telegram bot that helps you manage GitHub issues and repositories directly from Telegram. Authenticate with your GitHub account, select organizations or repositories, and create issues with ease. The bot also provides a web interface for OAuth login and supports secure storage of access tokens using PostgreSQL.

## Features
- **GitHub OAuth Integration**: Securely connect your GitHub account via Telegram.
- **Organization & Repository Selection**: Choose from your user account or organizations and their repositories.
- **Create Issues**: Quickly create GitHub issues from Telegram conversations.
- **Secure Token Storage**: Access tokens are stored securely in PostgreSQL.
- **Webhooks Support**: Easily verify and handle GitHub webhooks.
- **Support & Privacy Pages**: Simple web pages for privacy policy and support.

## Getting Started

### Prerequisites
- Docker & Docker Compose
- Telegram Bot Token
- GitHub OAuth App credentials
- PostgreSQL database

### Setup
1. **Clone the repository**
2. **Configure environment variables**: Copy `.env.example` to `.env` and fill in your credentials.
3. **Build and run with Docker Compose:**
   ```sh
   docker-compose up --build
   ```
4. **Start chatting with your bot on Telegram!**

## License
MIT License

## Support
For help or questions, contact with me or open an issue on GitHub.
