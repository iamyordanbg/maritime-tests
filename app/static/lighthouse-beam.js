(function(){
  var hero = document.querySelector('.hero');
  if(!hero) return;
  var pivot = document.getElementById('lampPivot');
  if(!pivot) return;
  var NATURAL_W = 1552, NATURAL_H = 1013;
  var LAMP_X = 395, LAMP_Y = 285;
  function positionPivot(){
    var cw = hero.clientWidth, ch = hero.clientHeight;
    var containerRatio = cw/ch, naturalRatio = NATURAL_W/NATURAL_H;
    var scale, offsetX = 0, offsetY = 0;
    if(containerRatio > naturalRatio){
      scale = cw/NATURAL_W;
      offsetY = (ch - NATURAL_H*scale)/2;
    } else {
      scale = ch/NATURAL_H;
      offsetX = (cw - NATURAL_W*scale)/2;
    }
    pivot.style.left = (offsetX + LAMP_X*scale) + 'px';
    pivot.style.top  = (offsetY + LAMP_Y*scale) + 'px';
    pivot.style.transform = 'scale(' + scale + ')';
    pivot.style.transformOrigin = '0 0';
  }
  positionPivot();
  window.addEventListener('resize', positionPivot);
  window.addEventListener('load', positionPivot);
})();
