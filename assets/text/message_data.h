#include "text/message_data.h"

/*
 * Web Remix: the Magnesis Rune (GI_REMIX_MAGNESIS, text id REMIX_TEXT_MAGNESIS in include/item.h), found in the
 * Lodestone Shrine. 0x7FA0 is not one of the game's own text ids (a duplicate would not link).
 */
DEFINE_MESSAGE(0x7FA0, TEXTBOX_TYPE_BLUE, TEXTBOX_POS_BOTTOM,
MSG(
"マグネキャッチをてにいれた！\n"
"[L]をおしつづけると　てつのものを\n"
"じりょくで　もちあげられる！"
)
,
MSG(
"You got the " COLOR(RED) "Magnesis Rune" COLOR(DEFAULT) "!\n"
"Hold [L] to grab iron things with\n"
"magnetic energy and lift them!"
BOX_BREAK
"Move what you hold with [Control-Pad],\n"
"lift or lower it with [C-Up] and [C-Down],\n"
"turn it with [C-Left] and [C-Right]."
BOX_BREAK
"Let go of [L] to drop it,\n"
"or press [B] to fling it away!"
)
,
MSG(
"You got the " COLOR(RED) "Magnesis Rune" COLOR(DEFAULT) "!\n"
"Hold [L] to grab iron things with\n"
"magnetic energy and lift them!"
)
,
MSG(
"You got the " COLOR(RED) "Magnesis Rune" COLOR(DEFAULT) "!\n"
"Hold [L] to grab iron things with\n"
"magnetic energy and lift them!"
)
)

/*
 * The following two messages should be kept last and in this order.
 * Message 0xFFFD must be last to not break the message debugger (see R_MESSAGE_DEBUGGER_TEXTID).
 * Message 0xFFFC must be immediately before message 0xFFFD to not break Font_LoadOrderedFont.
 */
DEFINE_MESSAGE_FFFC(0xFFFC, TEXTBOX_TYPE_BLACK, TEXTBOX_POS_VARIABLE,
MSG(
"０１２３４５６７８９あいうえおかきくけこ\n"
"さしすせそたちつてとなにぬねのはひふへほ\n"
"まみむめもやゆよらりるれろわをんぁぃぅぇ\n"
"ぉっゃゅょがぎぐげござじずぜぞだぢづでど\n"
"ばびぶべぼぱぴぷぺぽアイウエオカキクケコ\n"
"サシスセソタチツテトナニヌネノハヒフヘホ\n"
"マミムメモヤユヨラリルレロワヲンァィゥェ\n"
"ォッャュョガギグゲゴザジズゼゾダヂヅデド\n"
"バビブベボパピプペポヴＡＢＣＤＥＦＧＨＩ\n"
"ＪＫＬＭＮＯＰＱＲＳＴＵＶＷＸＹＺａｂｃ\n"
"ｄｅｆｇｈｉｊｋｌｍｎｏｐｑｒｓｔｕｖｗ\n"
"ｘｙｚ　┯？！：−（）゛゜，．／"
)
,
MSG(
"0123456789\n"
"ABCDEFGHIJKLMN\n"
"OPQRSTUVWXYZ\n"
"abcdefghijklmn\n"
"opqrstuvwxyz\n"
" -.\n"
)
,
MSG(/* UNUSED */)
,
MSG(/* UNUSED */)
)
DEFINE_MESSAGE(0xFFFD, TEXTBOX_TYPE_BLACK, TEXTBOX_POS_VARIABLE, MSG(), MSG(), MSG(), MSG())
