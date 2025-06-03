import asyncio
import logging
import os
import sqlite3
from urllib.parse import urlencode

import aiohttp
from aiohttp import web
from dotenv import load_dotenv
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    ApplicationBuilder,
    CallbackContext,
    CallbackQueryHandler,
    CommandHandler,
    ConversationHandler,
    MessageHandler,
    filters,
)

logger = logging.getLogger(__name__)

load_dotenv()

SQLITE_DB_PATH = 'tokens.sqlite3'
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
GITHUB_CLIENT_ID = os.getenv('GITHUB_CLIENT_ID')
GITHUB_CLIENT_SECRET = os.getenv('GITHUB_CLIENT_SECRET')
OAUTH_CALLBACK_DOMAIN = os.getenv('OAUTH_CALLBACK_DOMAIN')

OAUTH_CALLBACK_URL = f'https://{OAUTH_CALLBACK_DOMAIN}/callback'


def init_db():
    conn = sqlite3.connect(SQLITE_DB_PATH)
    c = conn.cursor()
    c.execute(
        '''CREATE TABLE IF NOT EXISTS user_tokens (
        telegram_id TEXT PRIMARY KEY,
        access_token TEXT NOT NULL
    )'''
    )
    conn.commit()
    conn.close()


def save_token(telegram_id, access_token):
    conn = sqlite3.connect(SQLITE_DB_PATH)
    c = conn.cursor()
    c.execute(
        'REPLACE INTO user_tokens (telegram_id, access_token) VALUES (?, ?)',
        (str(telegram_id), access_token),
    )
    conn.commit()
    conn.close()


def get_token(telegram_id):
    conn = sqlite3.connect(SQLITE_DB_PATH)
    c = conn.cursor()
    c.execute(
        'SELECT access_token FROM user_tokens WHERE telegram_id = ?',
        (str(telegram_id),),
    )
    row = c.fetchone()
    conn.close()
    return row[0] if row else None


SELECT_ACCOUNT, SELECT_PROJECT, GET_TITLE, GET_DESCRIPTION = range(4)


async def fetch_github_accounts(user_id=None):
    """Fetch the user's organizations and their own username."""
    token = get_token(user_id) if user_id else None
    headers = {'Authorization': f'token {token}'} if token else {}
    accounts = []
    async with aiohttp.ClientSession() as session:
        async with session.get('https://api.github.com/user', headers=headers) as resp:
            if resp.status == 200:
                user = await resp.json()
                accounts.append({'type': 'user', 'login': user['login']})

        async with session.get(
            'https://api.github.com/user/orgs', headers=headers
        ) as resp:
            if resp.status == 200:
                orgs = await resp.json()
                for org in orgs:
                    accounts.append({'type': 'org', 'login': org['login']})
            else:
                logger.error(
                    f"Failed to fetch organizations: {resp.status} - {await resp.text()}"
                )
    return accounts


async def fetch_github_repos(user_id=None, account=None):
    token = get_token(user_id) if user_id else None
    headers = {'Authorization': f'token {token}'} if token else {}
    if not account:
        return []
    if account['type'] == 'org':
        url = f'https://api.github.com/orgs/{account["login"]}/repos'
    else:
        url = f'https://api.github.com/users/{account["login"]}/repos'
    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers) as response:
            if response.status == 200:
                data = await response.json()
                return [repo['name'] for repo in data]
            else:
                return []


async def start(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    accounts = await fetch_github_accounts(user_id)
    if not accounts:
        await update.message.reply_text(
            'Failed to fetch organizations or user info from GitHub. Please check your token or login again with /login command.'
        )
        return ConversationHandler.END
    keyboard = [
        [
            InlineKeyboardButton(
                f"{a['login']} ({a['type']})",
                callback_data=a['login'] + ":" + a['type'],
            )
        ]
        for a in accounts
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        'Choose an organization or your user account:', reply_markup=reply_markup
    )
    return SELECT_ACCOUNT


async def select_account(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()
    login_type = query.data.split(":")
    account = {'login': login_type[0], 'type': login_type[1]}
    context.user_data['selected_account'] = account
    user_id = update.effective_user.id
    repo_list = await fetch_github_repos(user_id, account)
    if not repo_list:
        await query.edit_message_text('No repositories found for this account.')
        return ConversationHandler.END
    keyboard = [[InlineKeyboardButton(repo, callback_data=repo)] for repo in repo_list]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(
        'Choose a project to create an issue:', reply_markup=reply_markup
    )
    return SELECT_PROJECT


async def select_project(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()
    context.user_data['selected_repo'] = query.data
    await query.edit_message_text(
        text=f"Selected project: {query.data}.\nPlease provide the issue title:"
    )
    return GET_TITLE


async def get_title(update: Update, context: CallbackContext):
    context.user_data['title'] = update.message.text
    await update.message.reply_text('Please provide the issue description:')
    return GET_DESCRIPTION


async def get_description(update: Update, context: CallbackContext):
    context.user_data['description'] = update.message.text
    repo = context.user_data['selected_repo']
    title = context.user_data['title']
    description = context.user_data['description']
    user_id = update.effective_user.id
    token = get_token(user_id)
    account = context.user_data.get('selected_account')
    if not account:
        await update.message.reply_text(
            'Account selection missing. Please /start again.'
        )
        return ConversationHandler.END
    url = f'https://api.github.com/repos/{account["login"]}/{repo}/issues'
    issue_data = {'title': title, 'body': description}
    headers = {'Authorization': f'token {token}'} if token else {}
    async with aiohttp.ClientSession() as session:
        async with session.post(url, json=issue_data, headers=headers) as response:
            if response.status == 201:
                data = await response.json()
                await update.message.reply_text(
                    f'Issue created successfully! View it here: {data["html_url"]}'
                )
            else:
                await update.message.reply_text(
                    'Failed to create issue. Please check your GitHub token and repository permissions.'
                )
    return ConversationHandler.END


async def cancel(update: Update, context: CallbackContext):
    await update.message.reply_text('Operation canceled.')
    return ConversationHandler.END


async def login(update: Update, context: CallbackContext):
    telegram_id = update.effective_user.id
    params = {
        'client_id': GITHUB_CLIENT_ID,
        'redirect_uri': OAUTH_CALLBACK_URL,
        'scope': 'repo',
        'state': str(telegram_id),
        'allow_signup': 'true',
    }
    url = f'https://github.com/login/oauth/authorize?{urlencode(params)}'
    await update.message.reply_text(f'Login with GitHub: {url}')


async def oauth_callback(request):
    code = request.query.get('code')
    state = request.query.get('state')
    if not code or not state:
        return web.Response(text='Missing code or state', status=400)

    token_url = 'https://github.com/login/oauth/access_token'
    data = {
        'client_id': GITHUB_CLIENT_ID,
        'client_secret': GITHUB_CLIENT_SECRET,
        'code': code,
        'redirect_uri': OAUTH_CALLBACK_URL,
    }
    headers = {'Accept': 'application/json'}
    async with aiohttp.ClientSession() as session:
        async with session.post(token_url, data=data, headers=headers) as resp:
            token_data = await resp.json()
            access_token = token_data.get('access_token')
            if not access_token:
                return web.Response(text='Failed to get access token', status=400)
            save_token(state, access_token)
            return web.Response(
                text='GitHub login successful! You can return to Telegram.'
            )


def main():
    init_db()
    application = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    application.add_handler(CommandHandler('login', login))

    conversation_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            SELECT_ACCOUNT: [CallbackQueryHandler(select_account)],
            SELECT_PROJECT: [CallbackQueryHandler(select_project)],
            GET_TITLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_title)],
            GET_DESCRIPTION: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, get_description)
            ],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
    )

    application.add_handler(conversation_handler)

    async def start_web_app():
        app = web.Application()
        app.router.add_get('/callback', oauth_callback)
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, '0.0.0.0', 8080)
        await site.start()
        print(f'OAuth callback server running on {OAUTH_CALLBACK_URL}')

    loop = asyncio.get_event_loop()
    loop.create_task(start_web_app())
    application.run_polling()


if __name__ == '__main__':
    logging.basicConfig(
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        level=logging.DEBUG,
    )
    main()
