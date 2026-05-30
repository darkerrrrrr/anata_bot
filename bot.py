import os
import discord
from discord import app_commands
from discord.ext import commands
import io
import asyncio

# 【メッセージ入力画面（ポップアップ）】
class LetterModal(discord.ui.Modal):
    def __init__(self, is_anonymous: bool):
        self.is_anonymous = is_anonymous
        title_text = '送信設定：匿名（名前を隠す）' if is_anonymous else '送信設定：通常（名前を出す）'
        super().__init__(title=title_text)

        self.target_username = discord.ui.TextInput(
            label='送信相手のユーザー名', 
            placeholder='例: discord_user（@や表示名は不可、ユーザー名を入力）',
            max_length=32
        )
        self.letter_content = discord.ui.TextInput(
            label='メッセージ本文', 
            style=discord.TextStyle.long, 
            placeholder='送信したい文章を入力してください...',
            max_length=2000
        )
        
        self.add_item(self.target_username)
        self.add_item(self.letter_content)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        input_name = self.target_username.value.strip().lstrip('@')
        target_user = None

        for guild in interaction.client.guilds:
            member = guild.get_member_named(input_name)
            if not member:
                member = discord.utils.get(guild.members, display_name=input_name)
            if member:
                target_user = member
                break

        if not target_user:
            await interaction.followup.send(
                f"エラー：「{input_name}」というユーザーが見つかりませんでした。\n"
                "※Botと同じサーバーに所属し、正確なユーザー名である必要があります。", 
                ephemeral=True
            )
            return

        try:
            if self.is_anonymous:
                chat_message = "【匿名メッセージが届きました】"
                letter_title = "あなたへ、大切な想いが届いています"
            else:
                chat_message = f"【{interaction.user.name} さんからのメッセージが届きました】"
                letter_title = f"{interaction.user.name} さんより、大切な想いが届いています"
                
            plain_text_content = f"【{letter_title}】\n\n{self.letter_content.value}"

            file_data = io.BytesIO(plain_text_content.encode('utf-8'))
            discord_file = discord.File(fp=file_data, filename="letter.txt")
            
            await target_user.send(content=chat_message, file=discord_file)
            await interaction.followup.send(f"送信完了：{target_user.name} さんのDMへ届けました。", ephemeral=True)
            
        except discord.Forbidden:
            await interaction.followup.send("エラー：相手がDMを受信できない設定にしているため、送信できませんでした。", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"予期せぬエラーが発生しました: {e}", ephemeral=True)


# 【送信方法を選ぶボタン】
class SelectModeView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="匿名（名前を隠して送信）", style=discord.ButtonStyle.primary)
    async def anonymous_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(LetterModal(is_anonymous=True))

    @discord.ui.button(label="通常（名前を出して送信）", style=discord.ButtonStyle.success)
    async def name_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(LetterModal(is_anonymous=False))


# ─── Botの本体設定 ───
class MyBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.members = True          
        intents.message_content = True  
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        await self.tree.sync()

bot = MyBot()


# 🚀 /send コマンドの登録
@bot.tree.command(name="send", description="指定したユーザーのDMにメッセージ（テキストファイル）を送信します")
async def send_command(interaction: discord.Interaction):
    await interaction.response.send_message(
        "送信モードを選択してください：", 
        view=SelectModeView(), 
        ephemeral=True
    )


# 🛠️ !msgdel テキストコマンドの登録
@bot.command(name="msgdel")
async def msgdel_command(ctx, limit: int = 20):
    """過去ログからこのBotのメッセージを全消去し、打たれたコマンドの文字自体を削除します"""
    
    # 過去ログからBot自身のメッセージを全消去
    async for message in ctx.channel.history(limit=limit):
        if message.author == bot.user and message.id != ctx.message.id:
            try:
                await message.delete()
            except discord.DiscordException:
                pass

    # ユーザーが入力した「!msgdel」コマンド自体を削除（通知は出さずに終了）
    try:
        await ctx.message.delete()
    except discord.DiscordException:
        pass


@bot.event
async def on_ready():
    print(f"ログインしました: {bot.user.name}")

TOKEN = os.getenv("DISCORD_TOKEN")
if TOKEN:
    bot.run(TOKEN)
else:
    print("エラー：環境変数 DISCORD_TOKEN が設定されていません。")
