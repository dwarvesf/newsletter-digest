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
    async def wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except Exception as e:
            ctx = args[0] if isinstance(args[0], commands.Context) else args[1]
            logging.error(f"Error in command {func.__name__}: {str(e)}", exc_info=True)
            await ctx.send("Something went wrong. Please try again later.")
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
        embed.set_footer(text=f"Page {self.current_page + 1}/{len(self.articles) // self.per_page + 1}")

        for i, article in enumerate(current_articles, start=start+1):
            embed.add_field(
                name=f"{i}. {article['title']}",
                value=f"{article['url']}\n{article['description'][:160] + '...' if len(article['description']) > 160 else article['description']}",
                inline=False
            )

        return embed

    def update_button_states(self):
        if self.max_pages <= 1:
            return  # Don't update states if there's only one page
        self.previous_button.disabled = (self.current_page == 0)
        self.next_button.disabled = (self.current_page == self.max_pages - 1)

@bot.tree.command(name="fr", description="Fetch recent articles")
@app_commands.describe(
    days="Number of days to fetch articles from (default: 7)",
    all="Fetch all articles, including t`hose below the relevancy threshold (0 or 1, default: 0)",
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

    valid_criteria = get_search_criteria()
    if criteria and criteria not in valid_criteria:
        criteria_list = ", ".join(valid_criteria)
        await interaction.followup.send(f"Invalid criteria. Please choose from: {criteria_list}")
        return

    articles = fetch_articles_from_days(days)
    min_relevancy = get_min_relevancy_score()

    if all == 0:
        articles = [
            a for a in articles 
            if any(criterion['score'] >= min_relevancy for criterion in a['criteria'])
        ]

    if criteria:
        articles = [
            a for a in articles 
            if any(criterion['name'] == criteria for criterion in a['criteria'])
        ]

    if articles:
        # Sort by relevancy score. If criteria is provided, sort by THAT criteria score only
        # using the name of the criteria.
        if criteria:
            articles.sort(key=lambda x: next((criterion['score'] for criterion in x['criteria'] if criterion['name'] == criteria), 0), reverse=True)
        else:
            articles.sort(key=lambda x: x['criteria'][0]['score'], reverse=True)


        paginator = ArticlePaginator(articles, days)
        embed = paginator.create_embed()
        await interaction.followup.send(embed=embed, view=paginator)
    else:
        await interaction.followup.send("No articles found for the specified period.")

bot.run(TOKEN)
