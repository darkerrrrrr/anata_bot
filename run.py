import sys
import io
import discord

# 1. 届いたメッセージに付く「返信ボタン」の画面（View）を先に定義
class ReceiveReplyView(discord.ui.View):
    def __init__(self, original_sender_id: int):
        super().__init__(timeout=None)
        self.original_sender_id = original_sender_id

    @discord.ui.button(label="匿名で返信する", style=discord.ButtonStyle.primary)
    async def anonymous_reply(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(ReplyModal(self.original_sender_id, is_anonymous_reply=True))

    @discord.ui.button(label="名前を出して返信する", style=discord.ButtonStyle.success)
    async def name_reply(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(ReplyModal(self.original_sender_id, is_anonymous_reply=False))

# 2. ボタンを押したときに開く「返信入力画面」を定義
class ReplyModal(discord.ui.Modal):
    def __init__(self, original_sender_id: int, is_anonymous_reply: bool):
        self.original_sender_id = original_sender_id
        self.is_anonymous_reply = is_anonymous_reply
        title_text = '返信：匿名（名前を隠す）' if is_anonymous_reply else '返信：通常（名前を出す）'
        super().__init__(title=title_text)

        self.letter_content = discord.ui.TextInput(
            label='返信メッセージ本文', 
            style=discord.TextStyle.long, 
            placeholder='返信したい文章を入力してください...',
            max_length=2000
        )
        self.add_item(self.letter_content)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True, thinking=False)
        target_user = interaction.client.get_user(self.original_sender_id)
        if not target_user:
            await interaction.followup.send("❌ エラー：返信相手が見つかりませんでした。", ephemeral=True)
            return
        try:
            sender = "匿名" if self.is_anonymous_reply else f"{interaction.user.display_name}さん"
            chat_message = f"【{sender}より、大切な想いが届いています】"
            file_data = io.BytesIO(self.letter_content.value.encode('utf-8'))
            discord_file = discord.File(fp=file_data, filename="reply.txt")
            
            # 返信に対しても返信できるようにボタンを使い回す
            view = ReceiveReplyView(original_sender_id=interaction.user.id)
            await target_user.send(content=chat_message, file=discord_file, view=view)
            await interaction.followup.send(f"✅ 返信完了：相手のDMへ届けました。", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"⚠️ エラーが発生しました: {e}", ephemeral=True)

# 3. 最初の送信時（bot.pyの処理）に、返信ボタン（ReceiveReplyView）を強制的に合流させる処理
async def hooked_on_submit(self, interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True, thinking=False)
    input_name = self.target_username.value.strip().lstrip('@')
    target_user = None
    for guild in interaction.client.guilds:
        member = discord.utils.get(guild.members, name=input_name)
        if member:
            target_user = member
            break
    if not target_user:
        await interaction.followup.send(f"❌ エラー：「{input_name}」が見つかりませんでした。", ephemeral=True)
        return
    try:
        sender = "匿名" if self.is_anonymous else f"{interaction.user.display_name}さん"
        chat_message = f"【{sender}より、大切な想いが届いています】"
        file_data = io.BytesIO(self.letter_content.value.encode('utf-8'))
        discord_file = discord.File(fp=file_data, filename="letter.txt")
        
        # 💡 ここで作成した返信ボタン（View）を無理やり合流させて送信します
        view = ReceiveReplyView(original_sender_id=interaction.user.id)
        await target_user.send(content=chat_message, file=discord_file, view=view)
        await interaction.followup.send(f"✅ 送信完了：{target_user.display_name}さんのDMへ届けました。", ephemeral=True)
    except Exception as e:
        await interaction.followup.send(f"⚠️ エラーが発生しました: {e}", ephemeral=True)

# 4. bot.pyの中身をプログラム上で書き換える
import bot as original_bot
original_bot.LetterModal.on_submit = hooked_on_submit

# 5. あなたのbot.pyを起動
if __name__ == '__main__':
    # 元のbotが持っている起動処理をそのまま実行
    pass
