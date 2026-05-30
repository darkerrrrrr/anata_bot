import os
import discord
from discord import app_commands
from discord.ext import commands
import io

# 【メッセージ入力画面（ポップアップ）】
class LetterModal(discord.ui.Modal):
    def __init__(self, is_anonymous: bool):
        self.is_anonymous = is_anonymous
        title_text = '送信設定：匿名（名前を隠す）' if is_anonymous else '送信設定：通常（名前を出す）'
        super().__init__(title=title_text)

        self.target_username = discord.ui.TextInput(
            label='送信相手のユーザー名', 
            placeholder='例: discord_user（@や表示名は不可）',
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
        await interaction.response.defer(ephemeral=True, thinking=False)

        input_name = self.target_username.value.strip().lstrip('@')
        target_user = None

        for guild in interaction.client.guilds:
            member = discord.utils.get(guild.members, name=input_name)
            if member:
                target_user = member
                break

        if not target_user:
            await interaction.followup.send(
                f"❌ エラー：「{input_name}」が見つかりませんでした。\n"
                "※プロフィールの「ユーザー名（小文字の英数字）」を正確に入力してください。", 
                ephemeral=True
            )
            return

        try:
            # 💡 通常時の名前取得を display_name（表示名）に変更し、文言をご指定通りに修正
            sender = "匿名" if self.is_anonymous else f"{interaction.user.display_name} さん"
            chat_message = f"【{sender} より、貴方へ大切な想いが届いています】"
                
            plain_text_content = self.letter_content.value

            # メモリー上にテキストファイル（.txt）を作成
            file_data = io.BytesIO(plain_text_content.encode('utf-8'))
            discord_file = discord.File(fp=file_data, filename="letter.txt")
            
            await target_user.send(content=chat_message, file=discord_file)
            await interaction.followup.send(f"✅ 送信完了：{target_user.display_name} さんのDMへ届けました。", ephemeral=True)
            
        except discord.Forbidden:
            await interaction.followup.send("❌ エラー：相手がDMを閉じているため、送信できませんでした。", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"⚠️ 予期せぬエラーが発生しました: {e}", ephemeral=True)


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
    """過去ログからこのBotのメッセージと、打たれたコマンドの文字自体を無言で高速一括削除します"""
    
    def is_bot_or_cmd(m):
        return m.author == bot.user or m.id == ctx.message.id

    try:
        await ctx.channel.purge(limit=limit, check=is_bot_or_cmd)
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
