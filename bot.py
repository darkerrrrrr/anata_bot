import os
import discord
from discord import app_commands
from discord.ext import commands
import io

class LetterModal(discord.ui.Modal, title='大切な想いを届けるレター'):
    # 届ける相手のユーザー名を入力する欄
    target_username = discord.ui.TextInput(
        label='届ける相手のユーザー名', 
        placeholder='例: discord_user（@は不要です）',
        max_length=32
    )
    
    # 匿名か名前ありかを選択する欄
    anonymous_option = discord.ui.TextInput(
        label='送信モード（「匿名」か「名前」と入力）', 
        placeholder='匿名 にすると、あなたの名前は伏せられます。',
        max_length=2,
        default='匿名'
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

        input_name = self.target_username.value.strip().lstrip('@') # @が入力されても消去する
        target_user = None

        # Botが参加しているすべてのサーバーのメンバーから、ユーザー名が一致する人を探す
        for guild in interaction.client.guilds:
            member = guild.get_member_named(input_name)
            if member:
                target_user = member
                break # 見つかったらループを抜ける

        if not target_user:
            await interaction.followup.send(
                f"エラー：「{input_name}」というユーザーが見つかりませんでした。\n"
                "※Botと同じ共通のサーバーにいる人しか探すことができません。", 
                ephemeral=True
            )
            return

        try:
            # テキストファイルの中身を作る
            if self.anonymous_option.value == '名前':
                header = f"【差出人: {interaction.user.name} さんより、大切な想いが届いています】\n\n"
            else:
                header = f"【どなたかから、あなたへ大切な想いが届いています】\n\n"
                
            full_message = header + self.letter_content.value
            
            # メモリー上にテキストファイル（.txt）を作成
            file_data = io.BytesIO(full_message.encode('utf-8'))
            discord_file = discord.File(fp=file_data, filename="letter.txt")
            
            # 相手のDMに送信する
            await target_user.send("あなた宛てにメッセージが届きました。", file=discord_file)
            
            # 送信した本人に完了報告
            await interaction.followup.send(f"無事に {target_user.name} さんのDMへ想いを届けました！", ephemeral=True)
            
        except discord.Forbidden:
            await interaction.followup.send("エラー：相手がDMを閉じて留守にしているため、届けられませんでした。", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"予期せぬエラーが発生しました: {e}", ephemeral=True)

# ─── Botの本体設定 ───
class MyBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.members = True          # メンバー検索の権限をON
        intents.message_content = True  # !msgdel の発言内容を読み取る権限をON
        
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        await self.tree.sync()

bot = MyBot()

# /send コマンドの登録
@bot.tree.command(name="send", description="大切な人へメッセージをテキストファイルにして届けます")
async def send_command(interaction: discord.Interaction):
    await interaction.response.send_modal(LetterModal())

# !msgdel コマンドの登録
@bot.command(name="msgdel")
async def msgdel_command(ctx, limit: int = 100):
    """【全員実行可能】この「貴方の想い」Bot自身のメッセージだけを探して削除します"""
    deleted_count = 0
    
    # 処理中であることを伝えるメッセージ（これも「貴方の想い」Botの発言です）
    status_msg = await ctx.send("Botのメッセージを削除中...")
    
    # チャンネルの過去ログを取得（デフォルト100件）
    async for message in ctx.channel.history(limit=limit):
        # 💡 ここがポイント：メッセージの送信者が「このBot自身（bot.user）」の時だけ削除します
        if message.author == bot.user and message.id != status_msg.id:
            try:
                await message.delete()
                deleted_count += 1
            except discord.Forbidden:
                pass # 権限不足のエラーは無視する
                
    # 完了報告をして、その報告メッセージも自動で3秒後に消します
    await status_msg.edit(content=f"「貴方の想い」Botのメッセージを {deleted_count} 件削除しました。")
    await status_msg.delete(delay=3) # 3秒後に自動削除

@bot.event
async def on_ready():
    print(f"ログインしました: {bot.user.name}")

# 【GitHub用設定】環境変数 DISCORD_TOKEN からトークンを読み込む
TOKEN = os.getenv("DISCORD_TOKEN")
if TOKEN:
    bot.run(TOKEN)
else:
    print("エラー：環境変数 DISCORD_TOKEN が設定されていません。")
