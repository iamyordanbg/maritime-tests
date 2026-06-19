(function(){
  var hero=document.querySelector('.hero');
  var pivot=document.getElementById('lampPivot');
  if(!hero||!pivot) return;
  // Натурален размер на lighthouse-clean.jpg и позиция на лампата (пиксели в оригинала)
  var NW=1552,NH=1013,LX=395,LY=285;
  function pos(){
    var cw=hero.clientWidth,ch=hero.clientHeight;
    var containerRatio=cw/ch, naturalRatio=NW/NH;
    var isMobile=cw<=900;
    // На мобилен object-position се мести към фара (26% center) вместо center center,
    // затова изчисляваме offset-а по същата логика като CSS object-fit:cover.
    var focusX=isMobile?0.26:0.5, focusY=0.5;
    var scale,ox,oy;
    if(containerRatio>naturalRatio){
      scale=cw/NW;
      var visibleH=ch/scale;
      var cropTop=(NH-visibleH)*focusY;
      ox=0;
      oy=-cropTop*scale;
    } else {
      scale=ch/NH;
      var visibleW=cw/scale;
      var cropLeft=(NW-visibleW)*focusX;
      ox=-cropLeft*scale;
      oy=0;
    }
    pivot.style.left=(ox+LX*scale)+'px';
    pivot.style.top=(oy+LY*scale)+'px';
    pivot.style.transform='scale('+scale+')';
    pivot.style.transformOrigin='0 0';
  }
  pos();
  window.addEventListener('resize',pos);
  window.addEventListener('load',pos);
})();
