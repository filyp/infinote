
function! GoToTabWithBuffer(bufnr)
  let l:bufnr = a:bufnr
  let l:tabnr = tabpagenr()
  let l:totaltabs = tabpagenr('$')

  for l:tab in range(1, l:totaltabs)
    for l:win in range(1, tabpagewinnr(l:tab, '$'))
      if l:bufnr == winbufnr(win_getid(l:win, l:tab))
        execute l:tab . 'tabnext'
        execute l:win . 'wincmd w'
        return
      endif
    endfor
  endfor
  " If buffer is not found in any tab, keep the focus on the original tab.
  execute l:tabnr . 'tabnext'
endfunction


function! GetAllFolds()
  let l:folds = []
  let l:lineno = 1
  let l:endline = line('$')
  while l:lineno <= l:endline
    if foldclosed(l:lineno) != -1
      let l:start = foldclosed(l:lineno)
      let l:stop = foldclosedend(l:lineno)
      call add(l:folds, [l:start, l:stop])
      let l:lineno = l:stop + 1
    else
      let l:lineno = l:lineno + 1  
    endif
  endwhile
  return l:folds
endfunction

