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

/* Web Remix: the Temple of Two Truths (En_Remix_Time) */
DEFINE_MESSAGE(0x7FA1, TEXTBOX_TYPE_BLACK, TEXTBOX_POS_BOTTOM,
MSG(
"ふたつの　しんじつの　しんでん\n"
"まんなかの　とけいで　ときのうたを\n"
"ふけば　こどもと　おとなを　ゆききできる"
)
,
MSG(
"The " COLOR(RED) "Temple of Two Truths" COLOR(DEFAULT) ".\n"
"Play the " COLOR(BLUE) "Song of Time" COLOR(DEFAULT) " on the clock\n"
"at the heart of the hall to walk"
BOX_BREAK
"between the child and the adult.\n"
"What you move in one age stays\n"
"moved in the other..."
BOX_BREAK
"...but some things grow with the\n"
"years, and some wear away."
)
,
MSG(
"The " COLOR(RED) "Temple of Two Truths" COLOR(DEFAULT) ".\n"
"Play the " COLOR(BLUE) "Song of Time" COLOR(DEFAULT) " on the clock\n"
"at the heart of the hall to walk"
BOX_BREAK
"between the child and the adult.\n"
"What you move in one age stays\n"
"moved in the other..."
BOX_BREAK
"...but some things grow with the\n"
"years, and some wear away."
)
,
MSG(
"The " COLOR(RED) "Temple of Two Truths" COLOR(DEFAULT) ".\n"
"Play the " COLOR(BLUE) "Song of Time" COLOR(DEFAULT) " on the clock\n"
"at the heart of the hall to walk"
BOX_BREAK
"between the child and the adult.\n"
"What you move in one age stays\n"
"moved in the other..."
BOX_BREAK
"...but some things grow with the\n"
"years, and some wear away."
)
)

/* Web Remix: the Temple of Two Truths (En_Remix_Time) */
DEFINE_MESSAGE(0x7FA2, TEXTBOX_TYPE_BLACK, TEXTBOX_POS_BOTTOM,
MSG(
"きょう　うごかせないものも\n"
"きのうなら　うごかせるかもしれない"
)
,
MSG(
"What cannot be moved " COLOR(RED) "today" COLOR(DEFAULT) "\n"
"may be moved " COLOR(BLUE) "yesterday" COLOR(DEFAULT) "."
)
,
MSG(
"What cannot be moved " COLOR(RED) "today" COLOR(DEFAULT) "\n"
"may be moved " COLOR(BLUE) "yesterday" COLOR(DEFAULT) "."
)
,
MSG(
"What cannot be moved " COLOR(RED) "today" COLOR(DEFAULT) "\n"
"may be moved " COLOR(BLUE) "yesterday" COLOR(DEFAULT) "."
)
)

/* Web Remix: the Temple of Two Truths (En_Remix_Time) */
DEFINE_MESSAGE(0x7FA3, TEXTBOX_TYPE_BLUE, TEXTBOX_POS_BOTTOM,
MSG(
"みちは　ひらかれた。\n"
"だが　しんじつを　りかいしたか？"
)
,
MSG(
"You have opened the way.\n"
"But have you understood the truth?"
)
,
MSG(
"You have opened the way.\n"
"But have you understood the truth?"
)
,
MSG(
"You have opened the way.\n"
"But have you understood the truth?"
)
)

/* Web Remix: the Temple of Two Truths (En_Remix_Time) */
DEFINE_MESSAGE(0x7FA4, TEXTBOX_TYPE_BLACK, TEXTBOX_POS_BOTTOM,
MSG(
"おうごんの　たねが　ねむっている。\n"
"ひかりの　とどく　ところでだけ\n"
"めを　さます。"
)
,
MSG(
"A " COLOR(YELLOW) "golden seed" COLOR(DEFAULT) " sleeps here.\n"
"It wakes only where the sunlight\n"
"finds it."
)
,
MSG(
"A " COLOR(YELLOW) "golden seed" COLOR(DEFAULT) " sleeps here.\n"
"It wakes only where the sunlight\n"
"finds it."
)
,
MSG(
"A " COLOR(YELLOW) "golden seed" COLOR(DEFAULT) " sleeps here.\n"
"It wakes only where the sunlight\n"
"finds it."
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
