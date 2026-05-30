import discord
import io

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
            
            # 常に最新の送信者IDを引き継ぐView（ボタン）をセットして送信
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
        # 💡 ボタンが3分で期限切れエラーになるのを防ぐため、タイムアウトを完全に無効化
        super().__init__(timeout=None)
        self.original_sender_id = original_sender_id

    @discord.ui.button(label="匿名で返信する", style=discord.ButtonStyle.primary)
    async def anonymous_reply(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(ReplyModal(self.original_sender_id, is_anonymous_reply=True))

    @discord.ui.button(label="名前を出して返信する", style=discord.ButtonStyle.success)
    async def name_reply(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(ReplyModal(self.original_sender_id, is_anonymous_reply=False))
