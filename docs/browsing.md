# Browsing

## Folder URLs

Every folder has its own address. Opening `test` puts `/test/` in the address
bar, and going deeper gives `/test/deep/`, so the address always says where you
are.

Navigation uses the History API, so nothing reloads and back and forward work
the way they should. Folder names in the listing, the breadcrumb and the search
results are all real links, which means you can copy one, bookmark it, middle
click it into a new tab, or paste it to someone else and they land in the same
folder. Loading such a URL directly opens straight into that folder rather than
at the root.

A URL that does not resolve to a visible folder is a `404`, including one
pointing at a file, at something the ignore rules hide, or outside the served
directory. One that resolves but is denied by an [IAM rule](iam.md) is a `403`.

Behind authentication the sign in redirect keeps the folder, so `/test/deep/`
sends you to `/login?next=/test/deep/` and back again afterwards.

## The listing

Three columns: name, size, date modified. Click a heading to sort by it, click
again to reverse. Folders always sort above files.

Sizes are shown in whichever unit fits. A folder has no size and shows a dash.

The breadcrumb at the top is a path of links back to the root. The header on
the right shows the signed in user and, in form mode, a sign out button.

## File type icons

Files carry a small colour coded type badge, covering around 330 extensions
across code, web, config, databases, shells, archives, images, video, audio,
documents, executables, disk images, keys and fonts.

Compound extensions are understood, so `.tar.gz` and `.tar.bz2` get their own
badge rather than falling back to `.gz`. Extensionless names like `Dockerfile`,
`Makefile` and `LICENSE` are recognised by name, and dotfiles like `.env` and
`.bashrc` resolve by the part after the dot.

Anything unknown keeps the plain sheet. Adding more is one line in the matching
`registerTypes` call in `pyserve/assets/app.js`:

```javascript
registerTypes('code', {
  'ZG': ['zig'],
  'NM': ['nim'],
});
```

The label is at most three characters; the colour comes from the kind.

## Editing

Press and hold any row for two seconds to enter edit mode, the same gesture as
rearranging icons on a phone. Icons start wobbling, a delete badge appears next
to each entry, and names become editable.

- Click a name to rename it. Enter commits, Escape cancels.
- Drag an entry onto a folder to move it there.
- Click the red badge to delete. Deleting a folder is recursive and asks you to
  type the folder name to confirm.

Press Escape or click **Done** to leave edit mode.

Controls only appear where they are permitted. A row whose entry you may not
delete has no badge, a name you may not rename is not editable, and an entry
you may not move is not draggable. That reflects `READ_ONLY`, the individual
`ENABLE_*` settings, and any [IAM rules](iam.md) that apply to you.

## Downloads

Clicking a file downloads it. Downloads support HTTP range requests, so a
paused or interrupted download resumes rather than restarting, and a download
manager can fetch a large file in parallel chunks.

`ENABLE_DOWNLOAD=false` turns the route off entirely. Browsing still works;
file names are shown as plain text rather than links.

## Drag and drop

Dropping files anywhere on the page uploads them into the current folder.
Dropping onto a folder row uploads into that folder. A full page overlay names
the destination while you drag. See [Uploads](uploads.md).

## Design

The interface is deliberately plain: a monospace font, a paper background, no
framework, no build step. The whole frontend is four files under
`pyserve/assets/` totalling a few hundred lines, served from `/static` and
readable without tooling.

Reduced motion preferences are honoured: the edit mode wobble, the toast
animation and the new row highlight are all disabled when the browser asks for
reduced motion.

The layout collapses on narrow screens: the date column is dropped and the
corner panels span the width.
