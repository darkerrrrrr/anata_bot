import os
import discord
from discord import app_commands
from discord.ext import commands
import io

# ─── 1. 最初から順番に読み込めるように、クラスの定義をすべて上部に配置します ───

# 【メッセージ入力画面（モーダル）の定義】
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
        await interaction.response.defer(ephemeral=True) # 処理中マークを出す

        input_name = self.target_username.value.strip().lstrip('@')
        target_user = None

        # Botが参加しているすべてのサーバーのメンバーから、ユーザー名が一致する人を探す
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
            # 送信モードの判定（チャット画面への表示テキスト）
            if self.is_anonymous:
                chat_message = "【どなたかから、あなたへ大切な想いが届いています】"
            else:
                chat_message = f"【差出人: {interaction.user.name} さんより、大切な想いが届いています】"
                
            # txtファイルの中身はユーザーが打った純粋な本文だけにする
            pure_content = self.letter_content.value
            
            # メモリー上にテキストファイル（.txt）を作成
            file_data = io.BytesIO(pure_content.encode('utf-8'))
            discord_file = discord.File(fp=file_data, filename="letter.txt")
            
            # 相手のDMに、案内メッセージとファイルを一緒に送信する
            await target_user.send(content=chat_message, file=discord_file)
            
            # 送信した本人に完了報告（他の人には見えません）
            await interaction.followup.send(f"無事に {target_user.name} さんのDMへ想いを届けました！", ephemeral=True)
            
        except discord.Forbidden:
            await interaction.followup.send("エラー：相手がDMを閉じて留守にしているため、届けられませんでした。", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"予期せぬエラーが発生しました: {e}", ephemeral=True)


# 【送信モードの選択ボタンの定義】
class SelectModeView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="匿名で送る", style=discord.ButtonStyle.primary)
    async def anonymous_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(LetterModal(is_anonymous=True))

    @discord.ui.button(label="名前を出して送る", style=discord.ButtonStyle.success)
    async def name_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(LetterModal(is_anonymous=False))


# ─── 2. クラスの準備が終わったあとに、Botの本体設定を行います ───
class MyBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.members = True          # メンバー検索
        intents.message_content = True  # !msgdel テキストコマンドを読み取るためON
        
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        await self.tree.sync()

bot = MyBot()


# 🚀 /send コマンドの登録（事前に定義した SelectModeView を安全に呼び出せるようになりました）
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
    """一般ユーザー誰でも実行可能：過去ログからBotのメッセージだけを静かに全消去します"""
    
    # もしサーバー側で「メッセージの管理権限」がBotにあれば、その場でユーザーの「!msgdel」を即座に消します
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

    # 権限がないサーバーや、1対1のDM画面など、どうしてもあなたの「!msgdel」の文字が残ってしまう場合
    if not user_msg_deleted:
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
