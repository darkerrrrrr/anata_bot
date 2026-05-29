import os
import discord
from discord import app_commands
from discord.ext import commands
import io

# ─── 3. メッセージ削除後に表示される「セルフお掃除ボタン」 ───
class UserMessageDeleteView(discord.ui.View):
    def __init__(self, user_msg: discord.Message):
        super().__init__(timeout=60) # 1分経ったら自動でボタンを無効化します
        self.user_msg = user_msg

    # 「打ったコマンドの文字を消す」ボタン
    @discord.ui.button(label="自分の「!msgdel」の文字も消す", style=discord.ButtonStyle.danger, emoji="🧹")
    async def delete_user_message(self, interaction: discord.Interaction, button: discord.ui.Button):
        # 💡 【バグ修正】最初に「処理を受け付けました」という返答（レスポンス）を確定させます
        await interaction.response.defer(ephemeral=True)

        # 💡 【DM対応】fetch_messageを使わず、事前に受け取ったメッセージオブジェクトから直接削除
        try:
            await self.user_msg.delete()
        except discord.DiscordException:
            pass

        # 役目を終えたので、この案内ボタンが付いたBot自身のメッセージも完全に消滅させます
        try:
            await interaction.message.delete()
        except discord.DiscordException:
            pass

# ─── 2. ボタンを押した後に開く「メッセージ入力画面」 ───
class LetterModal(discord.ui.Modal):
    def __init__(self, is_anonymous: bool):
        self.is_anonymous = is_anonymous
        title_text = '大切な想いを届ける（匿名）' if is_anonymous else '大切な想いを届ける（名前あり）'
        super().__init__(title=title_text)

    # 届ける相手のユーザー名を入力する欄
    target_username = discord.ui.TextInput(
        label='届ける相手のユーザー名', 
        placeholder='例: discord_user（@は不要です）',
        max_length=32
    )
    
    # メッセージ本文を入力する欄
    letter_content = discord.ui.TextInput(
        label='伝えたい想い（本文）', 
        style=discord.TextStyle.long, 
        placeholder='ここにメッセージを書いてください...',
        max_length=2000
    )

    # 送信ボタンが押された時の処理
    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        input_name = self.target_username.value.strip().lstrip('@')
        target_user = None

        for guild in interaction.client.guilds:
            member = guild.get_member_named(input_name)
            if member:
                target_user = member
                break

        if not target_user:
            await interaction.followup.send(
                f"エラー：「{input_name}」というユーザーが見つかりませんでした。\n"
                "※Botと同じ共通のサーバーにいる人しか探すことができません。", 
                ephemeral=True
            )
            return

        try:
            if self.is_anonymous:
                chat_message = "【どなたかから、あなたへ大切な想いが届いています】"
            else:
                chat_message = f"【差出人: {interaction.user.name} さんより、大切な想いが届いています】"
                
            pure_content = self.letter_content.value
            
            file_data = io.BytesIO(pure_content.encode('utf-8'))
            discord_file = discord.File(fp=file_data, filename="letter.txt")
            
            await target_user.send(content=chat_message, file=discord_file)
            await interaction.followup.send(f"無事に {target_user.name} さんのDMへ想いを届けました！", ephemeral=True)
            
        except discord.Forbidden:
            await interaction.followup.send("エラー：相手がDMを閉じて留守にしているため、届けられませんでした。", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"予期せぬエラーが発生しました: {e}", ephemeral=True)

# ─── 1. 最初にチャット欄に表示される「送信モードの選択ボタン」 ───
class SelectModeView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="匿名で送る", style=discord.ButtonStyle.primary)
    async def anonymous_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(LetterModal(is_anonymous=True))

    @discord.ui.button(label="名前を出して送る", style=discord.ButtonStyle.success)
    async def name_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(LetterModal(is_anonymous=False))

# ─── Botの本体設定 ───
class MyBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.members = True          # メンバー検索
        intents.message_content = True  # !msgdel テキストコマンドを読み取るためON
        
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        await self.tree.sync()

bot = MyBot()

# /send コマンドの登録
@bot.tree.command(name="send", description="大切な人へメッセージをテキストファイルにして届けます")
async def send_command(interaction: discord.Interaction):
    await interaction.response.send_message(
        "メッセージの送信モードを選択してください：", 
        view=SelectModeView(), 
        ephemeral=True
    )

# 🛠️ !msgdel テキストコマンドの登録
@bot.command(name="msgdel")
async def msgdel_command(ctx, limit: int = 20):
    """一般ユーザー誰でも実行可能：DMでもサーバーでも権限不要で痕跡を消し去る仕組み"""
    
    # もしBotに「メッセージの管理権限」があれば、その場でユーザーの「!msgdel」を即座に消します
    try:
        await ctx.message.delete()
        user_msg_deleted = True
    except discord.DiscordException:
        # 権限がないサーバーやDM画面では、ここでは消さずにフラグを立てます
        user_msg_deleted = False

    # 過去ログからBot自身のメッセージをすべて削除する処理
    async for message in ctx.channel.history(limit=limit):
        if message.author == bot.user:
            try:
                await message.delete()
            except discord.DiscordException:
                pass

    # 💡 権限がなくてユーザーの「!msgdel」の文字が残ってしまっている場合のみ、
    # 修正された新しい「お掃除ボタン」を目の前に出します（メッセージそのものを引き渡します）。
    if not user_msg_deleted:
        await ctx.send(
            "お掃除が完了しました。下のボタンを押して、あなたの「!msgdel」の文字を完全に消去してください：", 
            view=UserMessageDeleteView(ctx.message)
        )

@bot.event
async def on_ready():
    print(f"ログインしました: {bot.user.name}")

# 【GitHub用設定】環境変数 DISCORD_TOKEN からトークンを読み込む
TOKEN = os.getenv("DISCORD_TOKEN")
if TOKEN:
    bot.run(TOKEN)
else:
    print("エラー：環境変数 DISCORD_TOKEN が設定されていません。")
