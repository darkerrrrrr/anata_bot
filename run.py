import sys
import io
import discord
from discord.ext import commands

# ─── 1. 返信ボタン（View）と返信画面（Modal）の定義 ───
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
            
            view = ReceiveReplyView(original_sender_id=interaction.user.id)
            await target_user.send(content=chat_message, file=discord_file, view=view)
            await interaction.followup.send(f"✅ 返信完了：相手のDMへ届けました。", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"⚠️ エラーが発生しました: {e}", ephemeral=True)


# ─── 2. bot.py の送信処理（on_submit）の直後に割り込んで、線を繋ぐフック処理 ───
# 💡 bot.py の処理が終わった後、この関数に処理が流れてきてボタンを上書き添付します
def create_hook(original_on_submit):
    async def hooked_on_submit(self, interaction: discord.Interaction):
        # まずは本来の bot.py にある送信処理を実行させる（線を繋ぐ）
        await original_on_submit(self, interaction)
        
        # 💡 bot.py の処理（送信）が終わった直後に、ここへ来ます
        # 送信相手のユーザーを再取得し、最後に送られたメッセージへ返信ボタン（View）を強制合流させます
        input_name = self.target_username.value.strip().lstrip('@')
        target_user = None
        for guild in interaction.client.guilds:
            member = discord.utils.get(guild.members, name=input_name)
            if member:
                target_user = member
                break
                
        if target_user:
            try:
                # 相手とのDM履歴から、直前にBotが送ったメッセージを特定
                async for msg in target_user.history(limit=5):
                    if msg.author == interaction.client.user:
                        # 期限切れにならない返信ボタン（View）を後付けで合流
                        view = ReceiveReplyView(original_sender_id=interaction.user.id)
                        await msg.edit(view=view)
                        break
            except Exception:
                pass
                
    return hooked_on_submit


# ─── 3. プログラム実行時に自動で仕掛けを連動させる ───
import bot as original_bot

# bot.py に書かれている LetterModal の送信処理の「後ろ」に、run.py の処理を繋ぎ替える
original_bot.LetterModal.on_submit = create_hook(original_bot.LetterModal.on_submit)


# ─── 4. 起動処理の引き継ぎ ───
if __name__ == '__main__':
    # bot.py の起動シーケンスをそのまま実行
    pass
