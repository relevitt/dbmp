"use strict";

/*
    This module is for dynamically applied tailwind styling.

    Some styling appears instead in tailwind_input.css, because
    it seemed easier to deal with it there, including:

    - progress bars
    - buttons
    - selected items

*/

W.css = {
  button_focus: `
        bg-gray-300
    `,
  cover_popup: `
        z-[102]
        [&_img]:cursor-pointer
        [&_img]:max-w-[500px]
        [&_img]:h-auto
    `,
  hidden: `
      hidden
    `,
  import_visible: `
        flex
    `,
  import_tooltip_visible: `
        block
    `,
  import_directory: `
        group-hover:cursor-pointer
        group-hover:underline
    `,
  import_file: `
        text-gray-600
    `,
  import_outcome: `
        overflow-automatic
    `,
  logging_entry_visible: `
        grid
    `,
  logging_color_default: `
      text-black
    `,
  logging_color_black: `
        text-black
    `,
  logging_color_white: `
        text-black
    `,
  logging_color_red: `
        text-red-500
    `,
  logging_color_green: `
        text-green-400
    `,
  logging_color_yellow: `
        text-yellow-500
    `,
  logging_color_blue: `
        text-blue-500
    `,
  logging_color_magenta: `
        text-violet-600
    `,
  logging_color_cyan: `
        text-cyan-300
    `,
  logging_visible: `
        flex
    `,
  menu_visible: `
        flex
    `,
  menu_selected: `
        bg-gray-300
    `,
  menu_locked: `
        text-gray-300
        cursor-default
        hover:bg-white
        after:content-none
    `,
  paginate_active: `
        bg-gray-300
    `,
  paginate_link: `
        underline
        cursor-pointer
    `,
  paginate_visible: `
        flex
    `,
  player_controls_vol: `
        fa-volume-up
    `,
  player_controls_muted: `
        fa-volume-mute
    `,
  player_controls_paused: `
        fa-play
    `,
  player_controls_playing: `
        fa-pause
    `,
  player_pointer: `
        cursor-pointer
    `,
  player_volume_on: `
        fa-volume-off
    `,
  player_volume_muted: `
        fa-volume-mute
    `,
  popup_visible: `
        block
    `,
  popup_title_wrap: `
        break-words
        whitespace-normal
        max-w-full
    `,
  popup_static: `
        cursor-grab
    `,
  popup_moving: `
        cursor-pointer
    `,
  popup_alertbar: `
        text-center
        font-bold
    `,
  qedit_visible: `
        flex
    `,
  qedit_dragging: `
        [&_div]:opacity-60
    `,
  qedit_dragover: `
        [&_div]:border-t-2
        [&_div]:border-dashed
        [&_div]:border-black
        [&_div]:mt-[1px]
        [&_div]:pt-[1px]
    `,
  qs_sonos_first_div: `
        mt-0
    `,
  qs_link: `
        cursor-pointer
        hover:underline
    `,
  qs_playing: `
        italic
        font-bold
    `,
  qs_selected: `
        [&>div:first-child]:bg-gray-300
    `,
  qs_menu_arrow: `
        bg-center
        bg-no-repeat
        bg-none
        lg:bg-[url('/icons/right.png')]
    `,
  qs_menu_showing: `
        !border-2
        !border-black
        rounded-md
        lg:!border-y-1
        lg:!border-gray-300
        lg:rounded-none
        lg:!border-x-[0px]
    `,
  quarantine_visible: `
        flex
    `,
  queue_top_menu: `
        after:ml-1
        after:content-[url('/icons/down.png')]
        after:align-[-10%]
        hover:border
        hover:border-gray-300
        hover:cursor-pointer
    `,
  queue_loaded: `
        lg:[&_span]:italic
        lg:[&_span]:font-bold
        [&_span.f1-outer]:lg:w-8
        [&_span.f1-outer]:lg:text-gray-300
        [&_span.f1-outer]:lg:bg-gray-300
        [&_span.f1-outer]:lg:bg-center
        [&_span.f1-outer]:lg:bg-no-repeat
        [&_span.f1]:lg:invisible
        [&_div.f7]:flex
        lg:[&_div.f7]:hidden
    `,
  queue_not_playing: `
        [&_span.f1-outer]:lg:!bg-[url('icons/play_white.png')]
        [&_div.f7_span.f71]:h-4
        [&_div.f7_span.f72]:h-2
        [&_div.f7_span.f73]:h-1
        [&_div.f7_span.f74]:h-2
        [&_div.f7_span.f75]:h-3
    `,
  queue_playing: `
        [&_span.f1-outer]:lg:!bg-[url('icons/pause_white.png')]
        [&_span.f1a]:bg-[url('icons/pause_white.png')]
        [&_div.f7_span.f71]:animate-bounce-eq
        [&_div.f7_span.f71]:[animation-delay:0s]
        [&_div.f7_span.f72]:animate-bounce-eq
        [&_div.f7_span.f72]:[animation-delay:0.2s]
        [&_div.f7_span.f73]:animate-bounce-eq
        [&_div.f7_span.f73]:[animation-delay:0.4s]
        [&_div.f7_span.f74]:animate-bounce-eq
        [&_div.f7_span.f74]:[animation-delay:0.3s]
        [&_div.f7_span.f75]:animate-bounce-eq
        [&_div.f7_span.f75]:[animation-delay:0.1s]
    `,
  queue_ul_not_dragged: `
        [&_li:not(:last-child):hover_span.f1-outer]:lg:w-8
        [&_li:not(:last-child):hover_span.f1-outer]:lg:bg-gray-300
        [&_li:not(:last-child):hover_span.f1-outer]:lg:bg-center
        [&_li:not(:last-child):hover_span.f1-outer]:lg:bg-no-repeat
        [&_li:not(:last-child):hover_span.f1-outer]:lg:bg-[url('icons/play_white.png')]
        [&_li:not(:last-child):hover_span.f1]:lg:opacity-0
    `,
  queue_f1_small: `
        w-[1.75em]
    `,
  queue_f1_large: `
        w-[3em]
    `,
  queue_dragging: `
        [&_div]:opacity-60
    `,
  queue_dragover: `
        [&_div]:border-t-dashed
        [&_div]:border-black
        [&_div]:mt-[1px]
        [&_div]:pt-[1px];
    `,
  queue_menu_showing: `
        !border-2
        !border-black
        rounded-md
    `,
  search_visible: `
        flex
    `,
  search_category_selected: `
        bg-gray-300
        font-bold
    `,
  search_menu_showing: `
        !border-2
        !border-black
        rounded-md
    `,
  search_image_not_fixed: `
        cursor-pointer
    `,
  search_image_fixed: `
        cursor-default
    `,
  search_track_highlight: `
        border
        first:!border-t
        !border-black
    `,
  search_track_hover_play: `
        group-hover:bg-[url('icons/play_white.png')]
        group-hover:text-[0]
        bg-[position:-5px_0]
    `,
  se_non_text_select: `
        select-none
    `,
  se_max_height: `
        max-h-[35vh]
    `,
  se_rename_tracks: `
        [&_li:hover]:bg-transparent
        [&_li:hover]:bg-none
        [&_input]:w-full
        [&_input]:h-[24px]
        [&_input]:text-[15px]
    `,
  se_dragging: `
        [&_span]:"opacity-30"
    `,
  se_dragover: `
        border-t
        border-dashed
        border-black
        mt-[1px]
        pt-[1px]
    `,
  shield_visible: `
        block
    `,
  st_selected: `
        bg-gray-300
    `,
  system_selected: `
        bg-gray-300
    `,
  util_dragicon: `
        absolute
        -z-20
        top-0
        right-0
        w-1/2
    `,
};

// Sanitize the W.css object to ensure no extra spaces or newlines in class strings
Object.keys(W.css).forEach((key) => {
  if (typeof W.css[key] === "string") {
    W.css[key] = W.css[key].replace(/\s+/g, " ").trim();
  }
});

// Utility function to add classes dynamically
W.css.addClasses = (element, ...styleKeys) => {
  styleKeys.forEach((styleKey) => {
    if (typeof styleKey === "string" && W.css[styleKey]) {
      const classList = W.css[styleKey];
      classList.split(/\s+/).forEach((cls) => {
        const cleanClass = cls.trim();
        if (cleanClass) {
          element.classList.add(cleanClass);
        }
      });
    } else {
      console.warn(`Style key "${styleKey}" does not exist in W.css.`);
    }
  });
};

// Utility function to remove classes dynamically
W.css.removeClasses = (element, ...styleKeys) => {
  styleKeys.forEach((styleKey) => {
    if (typeof styleKey === "string" && W.css[styleKey]) {
      const classList = W.css[styleKey];
      classList.split(/\s+/).forEach((cls) => {
        const cleanClass = cls.trim();
        if (cleanClass) {
          element.classList.remove(cleanClass);
        }
      });
    } else {
      console.warn(`Style key "${styleKey}" does not exist in W.css.`);
    }
  });
};
