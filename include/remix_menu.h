#ifndef REMIX_MENU_H
#define REMIX_MENU_H

struct PlayState;

// Web Remix in-game menu (src/code/z_remix_menu.c). Press D-pad Up during gameplay.
void RemixMenu_Update(struct PlayState* play);
void RemixMenu_Draw(struct PlayState* play);

#endif
