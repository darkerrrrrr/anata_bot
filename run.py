import io
import sys
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


# ─── 2. bot.py の送信処理の「真ん中」に割り込んで、ボタンを強制合流させる処理 ───
# 💡 bot.pyのコードは一切書き換えずに、送信する瞬間の線だけを奪い取ってボタンを仕込みます
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
        await interaction.followup.send(
            f"❌ エラー：「{input_name}」が見つかりませんでした。\n"
            "※プロフィールの「ユーザー名（小文字の英数字）」を正確に入力してください。", 
            ephemeral=True
        )
        return

    try:
        sender = "匿名" if self.is_anonymous else f"{interaction.user.display_name}さん"
        chat_message = f"【{sender}より、大切な想いが届いています】"
            
        plain_text_content = self.letter_content.value

        file_data = io.BytesIO(plain_text_content.encode('utf-8'))
        discord_file = discord.File(fp=file_data, filename="letter.txt")
        
        # 💡 bot.py の送信タイミングを上書きし、返信用のViewボタン（ReceiveReplyView）をここで強制合流
        view = ReceiveReplyView(original_sender_id=interaction.user.id)
        await target_user.send(content=chat_message, file=discord_file, view=view)
        
        await interaction.followup.send(f"✅ 送信完了：{target_user.display_name}さんのDMへ届けました。", ephemeral=True)
        
    except discord.Forbidden:
        await interaction.followup.send("❌ エラー：相手がDMを閉じているため、送信できませんでした。", ephemeral=True)
    except Exception as e:
        await interaction.followup.send(f"⚠️ 予期せぬエラーが発生しました: {e}", ephemeral=True)


# ─── 3. プログラム実行時に自動で bot.py の処理をすり替える ───
import bot as original_bot

# bot.py に書かれている LetterModal の送信処理そのものを、run.py のボタン機能付き処理に完全に入れ替えます
original_bot.LetterModal.on_submit = hooked_on_submit


# ─── 4. 起動処理の引き継ぎ ───
if __name__ == '__main__':
    pass
