import os
import discord
from discord import app_commands
from discord.ext import commands
import io

class LetterModal(discord.ui.Modal, title='大切な想いを届けるレター'):
    target_username = discord.ui.TextInput(
        label='届ける相手のユーザー名', 
        placeholder='例: discord_user（@は不要です）',
        max_length=32
    )
    
    anonymous_option = discord.ui.TextInput(
        label='送信モード（「匿名」か「名前」と入力）', 
        placeholder='匿名 にすると、あなたの名前は伏せられます。',
        max_length=2,
        default='匿名'
    )
    
    letter_content = discord.ui.TextInput(
        label='伝えたい想い（本文）', 
        style=discord.TextStyle.long, 
        placeholder='ここにメッセージを書いてください...',
        max_length=2000
    )

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
            if self.anonymous_option.value == '名前':
                chat_message = f"【差出人: {interaction.user.name} さんより、大切な想いが届いています】"
            else:
                chat_message = "【どなたかから、あなたへ大切な想いが届いています】"
                
            pure_content = self.letter_content.value
            
            file_data = io.BytesIO(pure_content.encode('utf-8'))
            discord_file = discord.File(fp=file_data, filename="letter.txt")
            
            await target_user.send(content=chat_message, file=discord_file)
            await interaction.followup.send(f"無事に {target_user.name} さんのDMへ想いを届けました！", ephemeral=True)
            
        except discord.Forbidden:
            await interaction.followup.send("エラー：相手がDMを閉じて留守にしているため、届けられませんでした。", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"予期せぬエラーが発生しました: {e}", ephemeral=True)

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
    # 最初にボタンを提示（ephemeral=True で実行した本人にしか見えないようにします）
    await interaction.response.send_message(
        "メッセージの送信モードを選択してください：", 
        view=SelectModeView(), 
        ephemeral=True
    )

class SelectModeView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="匿名で送る", style=discord.ButtonStyle.primary)
    async def anonymous_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(LetterModal(is_anonymous=True))

    @discord.ui.button(label="名前を出して送る", style=discord.ButtonStyle.success)
    async def name_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(LetterModal(is_anonymous=False))

# 🛠️ 【仕様の限界を超えた最終形】!msgdel コマンドの登録
@bot.command(name="msgdel")
async def msgdel_command(ctx, limit: int = 20):
    """一般ユーザー誰でも実行可能：過去ログからBotのメッセージだけを静かに全消去します"""
    
    # 💡 もしサーバー側で「メッセージの管理権限」がBotにあれば、その場でユーザーの「!msgdel」を即座に消します
    user_msg_deleted = False
    try:
        await ctx.message.delete()
        user_msg_deleted = True
    except discord.DiscordException:
        pass

    # 過去ログからBot自身のメッセージをすべて削除する処理
    async for message in ctx.channel.history(limit=limit):
        if message.author == bot.user:
            try:
                await message.delete()
            except discord.DiscordException:
                pass

    # 💡 権限がないサーバーや、1対1のDM画面など、どうしてもあなたの「!msgdel」の文字が残ってしまう場合
    if not user_msg_deleted:
        # あなたの打ったメッセージに対して「ゴミ箱」のリアクションを付けて、手動で消してねと合図を送り、
        # このシステムメッセージ自体は3秒後に自動で消滅します。
        try:
            await ctx.message.add_reaction("🗑️")
        except discord.DiscordException:
            pass
            
        await ctx.send("🧹 お掃除が完了しました！上の「!msgdel」の文字は、メッセージ右側の『…』メニューから手動で削除してください。", delete_after=5)

@bot.event
async def on_ready():
    print(f"ログインしました: {bot.user.name}")

# 【GitHub用設定】環境変数 DISCORD_TOKEN からトークンを読み込む
TOKEN = os.getenv("DISCORD_TOKEN")
if TOKEN:
    bot.run(TOKEN)
else:
    print("エラー：環境変数 DISCORD_TOKEN が設定されていません。")
