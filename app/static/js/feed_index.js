// app/static/js/feed_index.js
// Feed page — извлечена от app/templates/feed/index.html (Правило 1+2).
// Очаква window.FEED_DATA = {isLogged, hasSearchQuery}

const IS_LOGGED = window.FEED_DATA.isLogged;
let currentPostId = null;

function previewImage(input){
  if(input.files&&input.files[0]){
    const reader=new FileReader();
    reader.onload=e=>{ document.getElementById('previewImg').src=e.target.result; document.getElementById('imagePreview').style.display='block'; };
    reader.readAsDataURL(input.files[0]);
  }
}
function clearImage(){
  document.getElementById('pImage').value='';
  document.getElementById('imagePreview').style.display='none';
  document.getElementById('previewImg').src='';
}

function toggleSearch(){ const i=document.getElementById('searchInput'); i.classList.toggle('open'); if(i.classList.contains('open'))i.focus(); }
function closeSearch(){ document.getElementById('searchInput').classList.remove('open'); }
if (window.FEED_DATA.hasSearchQuery) document.getElementById('searchInput').classList.add('open');

function escH(s){ return String(s).replace(/&/g,'&amp;').replace(/\x3c/g,'&lt;').replace(/\x3e/g,'&gt;'); }

async function openPost(id){
  currentPostId=id;
  document.getElementById('readTitle').textContent='...';
  document.getElementById('readBody').innerHTML='<div style="text-align:center;padding:30px;color:#9ca3af"><i class="fa-solid fa-circle-notch fa-spin"></i></div>';
  document.getElementById('commentsWrap').style.display='none';
  document.getElementById('readOverlay').classList.add('open');
  document.body.style.overflow='hidden';

  const res=await fetch('/feed/post/'+id);
  const data=await res.json();
  document.getElementById('readTitle').textContent=data.title;
  document.getElementById('readBody').innerHTML=`
    ${data.image_url?`<img src="${data.image_url}" style="width:100%;border-radius:8px;margin-bottom:12px;max-height:220px;object-fit:cover">`:''}
    <p style="white-space:pre-wrap;line-height:1.7">${escH(data.body)}</p>`;
  document.getElementById('readMeta').innerHTML=`
    <span><i class="fa-regular fa-eye" style="margin-right:3px"></i>${data.views}</span>
    <span><i class="fa-regular fa-comment" style="margin-right:3px"></i>${data.comments.length}</span>
    <span>${data.time_ago}</span>`;
  document.getElementById('commentsWrap').style.display='block';
  renderComments(data.comments);
}

function renderComments(comments){
  const el=document.getElementById('commentsList');
  if(!comments.length){ el.innerHTML='<p style="font-size:11px;color:#9ca3af;text-align:center;padding:8px 18px">No comments yet</p>'; return; }
  el.innerHTML=comments.map(c=>`
    <div class="comment-item">
      <div class="c-avatar">${c.user[0].toUpperCase()}</div>
      <div><div class="c-name">${escH(c.user)} <span class="c-time">${c.time_ago}</span></div><div class="c-text">${escH(c.body)}</div></div>
    </div>`).join('');
}

async function submitComment(){
  if(!IS_LOGGED||!currentPostId) return;
  const inp=document.getElementById('rcInput'); const body=inp.value.trim(); if(!body) return;
  const res=await fetch('/feed/comment/'+currentPostId,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({body})});
  const data=await res.json(); if(data.error) return;
  inp.value='';
  const el=document.getElementById('commentsList');
  const p=el.querySelector('p'); if(p) p.remove();
  const div=document.createElement('div'); div.className='comment-item';
  div.innerHTML=`<div class="c-avatar">${data.user[0].toUpperCase()}</div><div><div class="c-name">${escH(data.user)} <span class="c-time">${data.time_ago}</span></div><div class="c-text">${escH(data.body)}</div></div>`;
  el.appendChild(div);
  const cnt=document.getElementById('ccount-'+currentPostId); if(cnt) cnt.textContent=parseInt(cnt.textContent||0)+1;
}

function closeRead(){ document.getElementById('readOverlay').classList.remove('open'); document.body.style.overflow=''; }

function sharePost(title){
  const url=window.location.href;
  if(navigator.share){ navigator.share({title:title||'MARADTEST News',url}).catch(()=>{}); }
  else { navigator.clipboard.writeText(url).then(()=>{ const t=document.getElementById('copyToast'); t.classList.add('show'); setTimeout(()=>t.classList.remove('show'),2000); }); }
}

// ADMIN
function openAdmin(){ const o=document.getElementById('adminOverlay'); o.style.display='flex'; document.body.style.overflow='hidden'; loadAdminPosts(); }
function closeAdmin(){ document.getElementById('adminOverlay').style.display='none'; document.body.style.overflow=''; }

async function loadAdminPosts(){
  const res=await fetch('/admin/feed/posts'); const posts=await res.json();
  const el=document.getElementById('adminPostsList');
  el.innerHTML=posts.length
    ? '<p style="font-size:10px;font-weight:700;color:#6b7280;margin-bottom:6px;text-transform:uppercase">Published</p>'+
      posts.map(p=>`<div class="apost-item"><span style="flex:1;color:#374151">${escH(p.title)} <span style="color:#9ca3af">(${p.comments})</span></span><button class="adel-btn" onclick="deletePost(${p.id})">✕</button></div>`).join('')
    : '<p style="font-size:11px;color:#9ca3af">No posts yet.</p>';
}

async function submitPost(){
  const title=document.getElementById('pTitle').value.trim();
  const body=document.getElementById('pBody').value.trim();
  const st=document.getElementById('adminStatus');
  if(!title||!body){ st.textContent='Title and content required.'; st.style.display='block'; return; }
  st.style.display='none';
  const fd=new FormData(); fd.append('title',title); fd.append('body',body);
  const img=document.getElementById('pImage').files[0]; if(img) fd.append('image',img);
  const res=await fetch('/admin/feed/post',{method:'POST',body:fd});
  const data=await res.json();
  if(data.ok){ document.getElementById('pTitle').value=''; document.getElementById('pBody').value=''; document.getElementById('pImage').value=''; location.reload(); }
}

async function deletePost(id){
  if(!confirm('Delete this post?')) return;
  await fetch('/admin/feed/post/'+id,{method:'DELETE'}); loadAdminPosts(); location.reload();
}

document.addEventListener('keydown',e=>{ if(e.key==='Escape'){ closeRead(); closeAdmin(); }});
