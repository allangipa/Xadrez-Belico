(function(){
  var hoje=new Date();hoje.setHours(0,0,0,0);
  document.querySelectorAll('[data-estreia]').forEach(function(el){
    var p=el.getAttribute('data-estreia').split('-'),d=new Date(+p[0],p[1]-1,+p[2]);
    if(d<=hoje){el.textContent=el.getAttribute('data-no-ar')||'No ar';el.classList.add('no-ar');}
  });
  var rv=document.querySelectorAll('.revela');
  if('IntersectionObserver' in window){
    var io=new IntersectionObserver(function(es){es.forEach(function(x){if(x.isIntersecting){x.target.classList.add('visto');io.unobserve(x.target)}})},{rootMargin:'0px 0px -8% 0px'});
    rv.forEach(function(x){io.observe(x)});
  } else rv.forEach(function(x){x.classList.add('visto')});
  var bar=document.querySelector('.progresso'),art=document.querySelector('.texto');
  if(bar&&art){var up=function(){var r=art.getBoundingClientRect(),t=r.height-innerHeight;bar.style.transform='scaleX('+Math.min(1,Math.max(0,-r.top/(t>0?t:1)))+')'};addEventListener('scroll',up,{passive:true});up();}
  var links=document.querySelectorAll('.indice a');
  if(links.length&&'IntersectionObserver' in window){
    var io2=new IntersectionObserver(function(es){es.forEach(function(x){if(x.isIntersecting){links.forEach(function(a){a.classList.toggle('ativo',a.getAttribute('href')==='#'+x.target.id)})}})},{rootMargin:'-20% 0px -70% 0px'});
    document.querySelectorAll('.texto h2[id]').forEach(function(h){io2.observe(h)});
  }
  var lupa=document.querySelector('.lupa');
  if(lupa){
    var li=lupa.querySelector('img'),lp=lupa.querySelector('p'),lb=lupa.querySelector('button'),ant=null;
    var fecha=function(){lupa.classList.remove('aberta');document.body.style.overflow='';if(ant)ant.focus()};
    document.querySelectorAll('.fig button').forEach(function(b){b.addEventListener('click',function(){
      ant=b;var im=b.querySelector('img');li.src=b.dataset.grande;li.alt=im.alt;lp.textContent=b.dataset.legenda;
      lupa.classList.add('aberta');document.body.style.overflow='hidden';lb.focus();
    })});
    lb.addEventListener('click',fecha);
    lupa.addEventListener('click',function(ev){if(ev.target===lupa)fecha()});
    addEventListener('keydown',function(ev){if(ev.key==='Escape'&&lupa.classList.contains('aberta'))fecha()});
  }
})();
