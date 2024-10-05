import os
from discord.ext import commands, tasks
from email_crawler import fetch_unread_emails, fetch_articles_from_days
from discord import Intents
from dotenv import load_dotenv
from config_manager import get_cron_frequency, get_min_relevancy_score, get_search_criteria
import logging
import functools
import discord
from discord import app_commands
import sys
import signal
import asyncio

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    handlers=[
        logging.FileHandler("newsletter_bot.log"),
        logging.StreamHandler()
    ]
)

load_dotenv()  # Load environment variables from .env file

# Load environment variables
TOKEN = os.getenv('DISCORD_TOKEN')

# Set up the bot
intents = Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='?', intents=intents)

def command_error_handler(func):
    @functools.wraps(func)
    async def wrapper(interaction: discord.Interaction, *args, **kwargs):
        try:
            return await func(interaction, *args, **kwargs)
        except Exception as e:
            logging.error(f"Error in command {func.__name__}: {str(e)}", exc_info=True)
            await interaction.followup.send("Something went wrong. Please try again later.")
    return wrapper

# Apply the wrapper to all commands
for command in bot.commands:
    command.callback = command_error_handler(command.callback)

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user}')
    if not fetch_unread_emails_task.is_running():
        fetch_unread_emails_task.start()  # Start the cron job

@tasks.loop(minutes=get_cron_frequency())  # Use cron frequency from config
async def fetch_unread_emails_task():
    print("Fetching unread emails")
    fetch_unread_emails()

class NewsletterBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(command_prefix='?', intents=intents)

    async def setup_hook(self):
        await self.tree.sync()

bot = NewsletterBot()

class ArticlePaginator(discord.ui.View):
    def __init__(self, articles, days):
        super().__init__(timeout=300)
        self.articles = articles
        self.days = days
        self.current_page = 0
        self.per_page = 10
        self.max_pages = (len(self.articles) - 1) // self.per_page + 1

        # Hide buttons if there's only one page
        if self.max_pages <= 1:
            self.previous_button.style = discord.ButtonStyle.gray
            self.previous_button.disabled = True
            self.previous_button.label = "\u200b"  # Invisible character
            self.next_button.style = discord.ButtonStyle.gray
            self.next_button.disabled = True
            self.next_button.label = "\u200b"  # Invisible character
            self.clear_items()  # Remove all items from the view

    @discord.ui.button(label="Previous", style=discord.ButtonStyle.gray, disabled=True)
    async def previous_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.current_page = max(0, self.current_page - 1)
        await self.update_message(interaction)

    @discord.ui.button(label="Next", style=discord.ButtonStyle.gray)
    async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.current_page = min(self.max_pages - 1, self.current_page + 1)
        await self.update_message(interaction)

    async def update_message(self, interaction: discord.Interaction):
        embed = self.create_embed()
        self.update_button_states()
        await interaction.response.edit_message(embed=embed, view=self)

    def create_embed(self):
        start = self.current_page * self.per_page
        end = start + self.per_page
        current_articles = self.articles[start:end]

        embed = discord.Embed(title=f"Articles from the last {self.days} days", color=0xFFA500)
        embed.set_footer(text=f"Page {self.current_page + 1}/{self.max_pages}")

        for i, article in enumerate(current_articles, start=start+1):
            embed.add_field(
                name=f"{i}. {article.title}",
                value=f"{article.url}\n{article.description[:160] + '...' if len(article.description) > 160 else article.description}",
                inline=False
            )

        return embed

    def update_button_states(self):
        if self.max_pages <= 1:
            return  # Don't update states if there's only one page
        self.previous_button.disabled = (self.current_page == 0)
        self.next_button.disabled = (self.current_page == self.max_pages - 1)

def group_criteria(criteria):
    grouped = get_search_criteria()
    return {group: [c.lower() for c in criteria if c.lower() in group.lower().split(', ')] for group in grouped}

@bot.tree.command(name="fr", description="Fetch recent articles")
@app_commands.describe(
    days="Number of days to fetch articles from (default: 7)",
    all="Fetch all articles, including those below the relevancy threshold (0 or 1, default: 0)",
    criteria="Filter articles by criteria (default: None)"
)
@command_error_handler
async def fr(interaction: discord.Interaction, days: int = 7, all: int = 0, criteria: str = None):
    await interaction.response.defer()

    if days < 1:
        await interaction.followup.send("Please provide a valid number of days (greater than 0).")
        return

    if all not in [0, 1]:
        await interaction.followup.send("The 'all' parameter must be either 0 or 1.")
        return

    valid_criteria = [c.lower() for group in get_search_criteria() for c in group.split(', ')]
    if criteria:
        criteria = criteria.lower()
        if criteria not in valid_criteria:
            grouped_criteria = group_criteria(valid_criteria)
            criteria_list = "\n".join([f"{', '.join(items)}" for group, items in grouped_criteria.items() if items])
            await interaction.followup.send(f"Invalid criteria. Please choose from:\n{criteria_list}")
            return

    articles = fetch_articles_from_days(days, criteria)

    min_relevancy = get_min_relevancy_score()

    if all == 0:
        articles = [
            a for a in articles 
            if any(criterion['score'] >= min_relevancy for criterion in a.criteria)
        ]

    if articles:
        # Sort by relevancy score. If criteria is provided, sort by THAT criteria score only
        if criteria:
            articles.sort(key=lambda x: next((criterion['score'] for criterion in x.criteria if criterion['name'].lower() == criteria), 0), reverse=True)
        else:
            articles.sort(key=lambda x: x.criteria[0]['score'], reverse=True)

        paginator = ArticlePaginator(articles, days)
        embed = paginator.create_embed()
        await interaction.followup.send(embed=embed, view=paginator)
    else:
        await interaction.followup.send("No articles found for the specified period.")

@bot.tree.command(name="memo-drafts", description="Generate memo drafts for recent articles")
@app_commands.describe(
    days="Number of days to fetch articles from (default: 7)",
    criteria="Generate memo for a specific criteria (default: None)"
)
@command_error_handler
async def memo_drafts(interaction: discord.Interaction, days: int = 7, criteria: str = None):
    await interaction.response.defer()

    if days < 1:
        await interaction.followup.send("Please provide a valid number of days (greater than 0).")
        return

    valid_criteria = [c.lower() for group in get_search_criteria() for c in group.split(', ')]
    if criteria:
        criteria = criteria.lower()
        if criteria not in valid_criteria:
            grouped_criteria = group_criteria(valid_criteria)
            criteria_list = "\n".join([f"{', '.join(items)}" for group, items in grouped_criteria.items() if items])
            await interaction.followup.send(f"Invalid criteria. Please choose from:\n{criteria_list}")
            return

    articles = fetch_articles_from_days(days, criteria)

    min_relevancy = get_min_relevancy_score()

    # Filter articles by minimum relevancy score
    articles = [
        a for a in articles 
        if any(criterion['score'] >= min_relevancy for criterion in a.criteria)
    ]

    if not articles:
        await interaction.followup.send("No relevant articles found for the specified period.")
        return

    # Generate memo drafts
    used_articles = set()
    if criteria:
        memo_draft, used_articles = generate_memo_draft(articles, criteria, used_articles=used_articles)
        memo_drafts = [memo_draft]
    else:
        top_criteria = valid_criteria[:3]
        memo_drafts = []
        for c in top_criteria:
            memo_draft, used_articles = generate_memo_draft(articles, c, used_articles=used_articles)
            memo_drafts.append(memo_draft)
        other_memo_draft, used_articles = generate_memo_draft(articles, "Other", valid_criteria[3:], used_articles=used_articles)
        memo_drafts.append(other_memo_draft)

    # Create and send embeds
    embeds = [create_memo_embed(memo) for memo in memo_drafts if memo['articles']]
    
    if embeds:
        await interaction.followup.send(embeds=embeds[:10])  # Discord allows max 10 embeds per message
    else:
        await interaction.followup.send("No memo drafts could be generated for the specified criteria and period.")

def generate_memo_draft(articles, criteria, other_criteria=None, used_articles=None):
    if used_articles is None:
        used_articles = set()

    if other_criteria:
        filtered_articles = [
            a for a in articles 
            if any(criterion['name'].lower() in [c.lower() for c in other_criteria] for criterion in a.criteria)
            and a.url not in used_articles
        ]
    else:
        filtered_articles = [
            a for a in articles 
            if any(criterion['name'].lower() == criteria.lower() for criterion in a.criteria)
            and a.url not in used_articles
        ]
    
    # Sort articles by relevancy score for the specific criteria
    filtered_articles.sort(
        key=lambda x: next((criterion['score'] for criterion in x.criteria if criterion['name'].lower() == criteria.lower()), 0),
        reverse=True
    )

    selected_articles = filtered_articles[:8]  # Top 8 articles
    used_articles.update(article.url for article in selected_articles)

    memo = {
        'criteria': criteria,
        'articles': [
            {
                'title': article.title,
                'description': article.description,
                'url': article.url
            }
            for article in selected_articles
        ]
    }

    return memo, used_articles

def create_memo_embed(memo):
    embed = discord.Embed(title=f"Memo Draft: {memo['criteria']}", color=0xFFFF00)
    
    for i, article in enumerate(memo['articles'][:3], start=1):
        embed.add_field(
            name=article['title'],
            value=f"{article['description']}\n[Read more]({article['url']})",
            inline=False
        )
    
    quick_links = "\n".join([f"- [{a['title']}]({a['url']})" for a in memo['articles'][3:8]])
    if quick_links:
        embed.add_field(name="Quick links", value=quick_links, inline=False)
    
    return embed

async def exit_handler(signum, frame):
    print("Received signal to exit. Shutting down...")
    await bot.close()
    for task in asyncio.all_tasks(loop=bot.loop):
        if task is not asyncio.current_task():
            task.cancel()
    await asyncio.gather(*asyncio.all_tasks(loop=bot.loop), return_exceptions=True)
    bot.loop.stop()

def signal_handler(signum, frame):
    bot.loop.create_task(exit_handler(signum, frame))

# Register the exit handler
signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

try:
    bot.run(TOKEN)
except Exception as e:
    print(f"Unhandled exception: {e}")
    sys.exit(1)
finally:
    if not bot.is_closed():
        bot.loop.run_until_complete(bot.close())
