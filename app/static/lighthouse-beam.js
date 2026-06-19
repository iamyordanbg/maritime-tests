(function(){
  var hero=document.querySelector('.hero');
  var pivot=document.getElementById('lampPivot');
  if(!hero||!pivot) return;
  // Натурален размер на lighthouse-clean.jpg и позиция на лампата (пиксели в оригинала)
  var NW=1552,NH=1013,LX=395,LY=285;
  function pos(){
    var cw=hero.clientWidth,ch=hero.clientHeight;
    var scale,ox=0,oy=0;
    if(cw/ch>NW/NH){scale=cw/NW;oy=(ch-NH*scale)/2;}
    else{scale=ch/NH;ox=(cw-NW*scale)/2;}
    pivot.style.left=(ox+LX*scale)+'px';
    pivot.style.top=(oy+LY*scale)+'px';
    pivot.style.transform='scale('+scale+')';
    pivot.style.transformOrigin='0 0';
  }
  pos();
  window.addEventListener('resize',pos);
  window.addEventListener('load',pos);
})();
