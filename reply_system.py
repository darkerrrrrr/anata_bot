import discord
import io
from discord.ext import commands

# ─── 返信入力用のポップアップ画面（Modal） ───
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
            await interaction.followup.send("❌ エラー：返信相手のユーザーが見つかりませんでした。", ephemeral=True)
            return

        try:
            sender = "匿名" if self.is_anonymous_reply else f"{interaction.user.display_name}さん"
            chat_message = f"【{sender}より、大切な想いが届いています】"
                
            plain_text_content = self.letter_content.value

            file_data = io.BytesIO(plain_text_content.encode('utf-8'))
            discord_file = discord.File(fp=file_data, filename="reply.txt")
            
            view = ReceiveReplyView(original_sender_id=interaction.user.id)
            await target_user.send(content=chat_message, file=discord_file, view=view)
            
            await interaction.followup.send(f"✅ 返信完了：相手のDMへ届けました。", ephemeral=True)
            
        except discord.Forbidden:
            await interaction.followup.send("❌ エラー：相手がDMを閉じているため、返信できませんでした。", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"⚠️ 予期せぬエラーが発生しました: {e}", ephemeral=True)


# ─── 届いたメッセージに付く「返信方法を選ぶボタン」（View） ───
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


# ─── 【最初】のメッセージ入力画面（Modal） ───
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
            sender = "匿名" if self.is_anonymous else f"{interaction.user.display_name}さん"
            chat_message = f"【{sender}より、大切な想いが届いています】"
                
            plain_text_content = self.letter_content.value

            file_data = io.BytesIO(plain_text_content.encode('utf-8'))
            discord_file = discord.File(fp=file_data, filename="letter.txt")
            
            view = ReceiveReplyView(original_sender_id=interaction.user.id)
            await target_user.send(content=chat_message, file=discord_file, view=view)
            
            await interaction.followup.send(f"✅ 送信完了：{target_user.display_name}さんのDMへ届けました。", ephemeral=True)
            
        except discord.Forbidden:
            await interaction.followup.send("❌ エラー：相手がDMを閉じているため、送信できませんでした。", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"⚠️ 予期せぬエラーが発生しました: {e}", ephemeral=True)


# ─── 【最初】の送信方法を選ぶボタン（View） ───
class SelectModeView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="匿名（名前を隠して送信）", style=discord.ButtonStyle.primary)
    async def anonymous_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(LetterModal(is_anonymous=True))

    @discord.ui.button(label="通常（名前を出して送信）", style=discord.ButtonStyle.success)
    async def name_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(LetterModal(is_anonymous=False))


# 💡 【重要】bot.py側がメインスクリプトから自動インポートされた際、
# bot.pyの中にある古い「LetterModal」を、このファイルの返信機能付きに強制的に上書き差し替えします。
import sys
if 'bot' in sys.modules:
    sys.modules['bot'].LetterModal = LetterModal
