"use strict";(()=>{var He=Object.create;var me=Object.defineProperty;var ze=Object.getOwnPropertyDescriptor;var $e=Object.getOwnPropertyNames;var je=Object.getPrototypeOf,Ve=Object.prototype.hasOwnProperty;var q=(t,e)=>()=>(e||t((e={exports:{}}).exports,e),e.exports);var Xe=(t,e,r,o)=>{if(e&&typeof e=="object"||typeof e=="function")for(let n of $e(e))!Ve.call(t,n)&&n!==r&&me(t,n,{get:()=>e[n],enumerable:!(o=ze(e,n))||o.enumerable});return t};var J=(t,e,r)=>(r=t!=null?He(je(t)):{},Xe(e||!t||!t.__esModule?me(r,"default",{value:t,enumerable:!0}):r,t));var Ee=q(m=>{"use strict";var P=Symbol.for("react.element"),Ke=Symbol.for("react.portal"),Ye=Symbol.for("react.fragment"),Ze=Symbol.for("react.strict_mode"),Je=Symbol.for("react.profiler"),Qe=Symbol.for("react.provider"),et=Symbol.for("react.context"),tt=Symbol.for("react.forward_ref"),ot=Symbol.for("react.suspense"),rt=Symbol.for("react.memo"),nt=Symbol.for("react.lazy"),pe=Symbol.iterator;function at(t){return t===null||typeof t!="object"?null:(t=pe&&t[pe]||t["@@iterator"],typeof t=="function"?t:null)}var ge={isMounted:function(){return!1},enqueueForceUpdate:function(){},enqueueReplaceState:function(){},enqueueSetState:function(){}},be=Object.assign,ve={};function M(t,e,r){this.props=t,this.context=e,this.refs=ve,this.updater=r||ge}M.prototype.isReactComponent={};M.prototype.setState=function(t,e){if(typeof t!="object"&&typeof t!="function"&&t!=null)throw Error("setState(...): takes an object of state variables to update or a function which returns an object of state variables.");this.updater.enqueueSetState(this,t,e,"setState")};M.prototype.forceUpdate=function(t){this.updater.enqueueForceUpdate(this,t,"forceUpdate")};function xe(){}xe.prototype=M.prototype;function ee(t,e,r){this.props=t,this.context=e,this.refs=ve,this.updater=r||ge}var te=ee.prototype=new xe;te.constructor=ee;be(te,M.prototype);te.isPureReactComponent=!0;var de=Array.isArray,we=Object.prototype.hasOwnProperty,oe={current:null},ye={key:!0,ref:!0,__self:!0,__source:!0};function Se(t,e,r){var o,n={},a=null,i=null;if(e!=null)for(o in e.ref!==void 0&&(i=e.ref),e.key!==void 0&&(a=""+e.key),e)we.call(e,o)&&!ye.hasOwnProperty(o)&&(n[o]=e[o]);var s=arguments.length-2;if(s===1)n.children=r;else if(1<s){for(var l=Array(s),u=0;u<s;u++)l[u]=arguments[u+2];n.children=l}if(t&&t.defaultProps)for(o in s=t.defaultProps,s)n[o]===void 0&&(n[o]=s[o]);return{$$typeof:P,type:t,key:a,ref:i,props:n,_owner:oe.current}}function lt(t,e){return{$$typeof:P,type:t.type,key:e,ref:t.ref,props:t.props,_owner:t._owner}}function re(t){return typeof t=="object"&&t!==null&&t.$$typeof===P}function st(t){var e={"=":"=0",":":"=2"};return"$"+t.replace(/[=:]/g,function(r){return e[r]})}var he=/\/+/g;function Q(t,e){return typeof t=="object"&&t!==null&&t.key!=null?st(""+t.key):e.toString(36)}function W(t,e,r,o,n){var a=typeof t;(a==="undefined"||a==="boolean")&&(t=null);var i=!1;if(t===null)i=!0;else switch(a){case"string":case"number":i=!0;break;case"object":switch(t.$$typeof){case P:case Ke:i=!0}}if(i)return i=t,n=n(i),t=o===""?"."+Q(i,0):o,de(n)?(r="",t!=null&&(r=t.replace(he,"$&/")+"/"),W(n,e,r,"",function(u){return u})):n!=null&&(re(n)&&(n=lt(n,r+(!n.key||i&&i.key===n.key?"":(""+n.key).replace(he,"$&/")+"/")+t)),e.push(n)),1;if(i=0,o=o===""?".":o+":",de(t))for(var s=0;s<t.length;s++){a=t[s];var l=o+Q(a,s);i+=W(a,e,r,l,n)}else if(l=at(t),typeof l=="function")for(t=l.call(t),s=0;!(a=t.next()).done;)a=a.value,l=o+Q(a,s++),i+=W(a,e,r,l,n);else if(a==="object")throw e=String(t),Error("Objects are not valid as a React child (found: "+(e==="[object Object]"?"object with keys {"+Object.keys(t).join(", ")+"}":e)+"). If you meant to render a collection of children, use an array instead.");return i}function N(t,e,r){if(t==null)return t;var o=[],n=0;return W(t,o,"","",function(a){return e.call(r,a,n++)}),o}function it(t){if(t._status===-1){var e=t._result;e=e(),e.then(function(r){(t._status===0||t._status===-1)&&(t._status=1,t._result=r)},function(r){(t._status===0||t._status===-1)&&(t._status=2,t._result=r)}),t._status===-1&&(t._status=0,t._result=e)}if(t._status===1)return t._result.default;throw t._result}var R={current:null},H={transition:null},ut={ReactCurrentDispatcher:R,ReactCurrentBatchConfig:H,ReactCurrentOwner:oe};function Re(){throw Error("act(...) is not supported in production builds of React.")}m.Children={map:N,forEach:function(t,e,r){N(t,function(){e.apply(this,arguments)},r)},count:function(t){var e=0;return N(t,function(){e++}),e},toArray:function(t){return N(t,function(e){return e})||[]},only:function(t){if(!re(t))throw Error("React.Children.only expected to receive a single React element child.");return t}};m.Component=M;m.Fragment=Ye;m.Profiler=Je;m.PureComponent=ee;m.StrictMode=Ze;m.Suspense=ot;m.__SECRET_INTERNALS_DO_NOT_USE_OR_YOU_WILL_BE_FIRED=ut;m.act=Re;m.cloneElement=function(t,e,r){if(t==null)throw Error("React.cloneElement(...): The argument must be a React element, but you passed "+t+".");var o=be({},t.props),n=t.key,a=t.ref,i=t._owner;if(e!=null){if(e.ref!==void 0&&(a=e.ref,i=oe.current),e.key!==void 0&&(n=""+e.key),t.type&&t.type.defaultProps)var s=t.type.defaultProps;for(l in e)we.call(e,l)&&!ye.hasOwnProperty(l)&&(o[l]=e[l]===void 0&&s!==void 0?s[l]:e[l])}var l=arguments.length-2;if(l===1)o.children=r;else if(1<l){s=Array(l);for(var u=0;u<l;u++)s[u]=arguments[u+2];o.children=s}return{$$typeof:P,type:t.type,key:n,ref:a,props:o,_owner:i}};m.createContext=function(t){return t={$$typeof:et,_currentValue:t,_currentValue2:t,_threadCount:0,Provider:null,Consumer:null,_defaultValue:null,_globalName:null},t.Provider={$$typeof:Qe,_context:t},t.Consumer=t};m.createElement=Se;m.createFactory=function(t){var e=Se.bind(null,t);return e.type=t,e};m.createRef=function(){return{current:null}};m.forwardRef=function(t){return{$$typeof:tt,render:t}};m.isValidElement=re;m.lazy=function(t){return{$$typeof:nt,_payload:{_status:-1,_result:t},_init:it}};m.memo=function(t,e){return{$$typeof:rt,type:t,compare:e===void 0?null:e}};m.startTransition=function(t){var e=H.transition;H.transition={};try{t()}finally{H.transition=e}};m.unstable_act=Re;m.useCallback=function(t,e){return R.current.useCallback(t,e)};m.useContext=function(t){return R.current.useContext(t)};m.useDebugValue=function(){};m.useDeferredValue=function(t){return R.current.useDeferredValue(t)};m.useEffect=function(t,e){return R.current.useEffect(t,e)};m.useId=function(){return R.current.useId()};m.useImperativeHandle=function(t,e,r){return R.current.useImperativeHandle(t,e,r)};m.useInsertionEffect=function(t,e){return R.current.useInsertionEffect(t,e)};m.useLayoutEffect=function(t,e){return R.current.useLayoutEffect(t,e)};m.useMemo=function(t,e){return R.current.useMemo(t,e)};m.useReducer=function(t,e,r){return R.current.useReducer(t,e,r)};m.useRef=function(t){return R.current.useRef(t)};m.useState=function(t){return R.current.useState(t)};m.useSyncExternalStore=function(t,e,r){return R.current.useSyncExternalStore(t,e,r)};m.useTransition=function(){return R.current.useTransition()};m.version="18.3.1"});var ne=q((Ot,Le)=>{"use strict";Le.exports=Ee()});var _e=q(z=>{"use strict";var ct=ne(),ft=Symbol.for("react.element"),mt=Symbol.for("react.fragment"),pt=Object.prototype.hasOwnProperty,dt=ct.__SECRET_INTERNALS_DO_NOT_USE_OR_YOU_WILL_BE_FIRED.ReactCurrentOwner,ht={key:!0,ref:!0,__self:!0,__source:!0};function Ce(t,e,r){var o,n={},a=null,i=null;r!==void 0&&(a=""+r),e.key!==void 0&&(a=""+e.key),e.ref!==void 0&&(i=e.ref);for(o in e)pt.call(e,o)&&!ht.hasOwnProperty(o)&&(n[o]=e[o]);if(t&&t.defaultProps)for(o in e=t.defaultProps,e)n[o]===void 0&&(n[o]=e[o]);return{$$typeof:ft,type:t,key:a,ref:i,props:n,_owner:dt.current}}z.Fragment=mt;z.jsx=Ce;z.jsxs=Ce});var ae=q((Dt,ke)=>{"use strict";ke.exports=_e()});var V=J(ne());var _t=J(ae()),Ae={tileSize:256,logoScale:.7,finalScale:.69,logoOffset:[0,0],iconPlate:!1,keepPlate:!1,originalColors:!1,opticalDepth:1.1,dispersion:1.7,colorBleed:1.25,doubleBevel:1,bevelWidth:.14,corner:4.8,cornerPull:2.1,cornerWidth:2.2,cornerFocus:.58,edgeSmear:2.85,stretch:0,tilt:.35,bulge:1,specular:1,halo:0,shadow:1,ripple:1,bounce:0,response:.42,startSize:.2,startZoom:2.6,glide:2.3,present:2.4,drift:.12,swell:.5,focus:1,sheen:1,lightTurn:.9,hold:1,background:"#e9e9eb",plateColor:"#ffffff",logoColor:"#0e1428"},Ie={light:Ae,dark:{...Ae,logoScale:.72,finalScale:1,iconPlate:!0,halo:1,shadow:0,ripple:.5,startZoom:1.6,drift:.05,opticalDepth:.75,bevelWidth:.22,dispersion:.9,colorBleed:.45,corner:5,cornerPull:1.4,edgeSmear:1.2,tilt:0,cornerWidth:1.2,cornerFocus:.4,background:"#000000",plateColor:"#05070b",logoColor:"#ffffff"}},f=1024,B=.75;function gt(t){return new Promise((e,r)=>{let o=new Image;t.startsWith("data:")||(o.crossOrigin="anonymous"),o.onload=()=>e(o),o.onerror=()=>r(new Error("GlassIconReveal: the logo could not be loaded")),o.src=t})}function bt(t){return t.trimStart().startsWith("<")}function vt(t){let e=new DOMParser().parseFromString(t,"image/svg+xml").documentElement;if(!e||e.nodeName.toLowerCase()!=="svg")throw new Error("GlassIconReveal: the SVG could not be read");let r=parseFloat(e.getAttribute("width")||""),o=parseFloat(e.getAttribute("height")||""),n=(e.getAttribute("viewBox")||"").split(/[\s,]+/).map(Number);n.length===4&&n[2]>0&&n[3]>0&&([r,o]=[n[2],n[3]]),r>0&&o>0||(r=o=100);let a=f/Math.max(r,o);e.setAttribute("width",String(Math.round(r*a))),e.setAttribute("height",String(Math.round(o*a)));let i=new XMLSerializer().serializeToString(e).replace(/currentColor/g,"#ffffff");return"data:image/svg+xml;charset=utf-8,"+encodeURIComponent(i)}var xt=t=>bt(t)?vt(t):t;function wt(t,e,r){let o=document.createElement("canvas");o.width=o.height=f;let n=o.getContext("2d",{willReadFrequently:!0}),a=Math.min(f/e,f/r),i=(f-e*a)/2,s=(f-r*a)/2;n.drawImage(t,i,s,e*a,r*a);let l=n.getImageData(0,0,f,f).data,u=!0;for(let h=3;h<l.length;h+=388)if(l[h]<250){u=!1;break}let c=[l[0],l[1],l[2]],v=(h,d,y)=>Math.min(1,Math.max(0,(Math.hypot(h-c[0],d-c[1],y-c[2])/441-.08)/.2)),g=f,x=f,_=-1,p=-1;for(let h=0;h<f;h++)for(let d=0;d<f;d++){let y=(h*f+d)*4;(u?v(l[y],l[y+1],l[y+2])*255:l[y+3])>8&&(d<g&&(g=d),d>_&&(_=d),h<x&&(x=h),h>p&&(p=h))}if(_<0)throw new Error("GlassIconReveal: the logo is empty");let b=_-g+1,w=p-x+1,L=f*B/Math.max(b,w),E=document.createElement("canvas");E.width=E.height=f;let C=E.getContext("2d",{willReadFrequently:!0});if(C.imageSmoothingQuality="high",C.drawImage(t,f/2-(g+b/2-i)*L,f/2-(x+w/2-s)*L,e*a*L,r*a*L),u){let h=C.getImageData(0,0,f,f),d=h.data;for(let y=0;y<d.length;y+=4)d[y+3]=Math.round(d[y+3]*v(d[y],d[y+1],d[y+2]));C.putImageData(h,0,0)}return E}function yt(t){let e=f*f,r=t.getContext("2d",{willReadFrequently:!0}).getImageData(0,0,f,f).data,o=1e20,n=new Float64Array(e),a=new Float64Array(e);for(let c=0;c<e;c++){let v=r[c*4+3]/255;if(v>=1)n[c]=0,a[c]=o;else if(v<=0)n[c]=o,a[c]=0;else{let g=.5-v;n[c]=g>0?g*g:0,a[c]=g<0?g*g:0}}let i=new Float64Array(f),s=new Float64Array(f+1),l=new Uint16Array(f);Te(n,i,l,s,o),Te(a,i,l,s,o);let u=new Float32Array(e);for(let c=0;c<e;c++)u[c]=(Math.sqrt(n[c])-Math.sqrt(a[c]))/f;return u}function Te(t,e,r,o,n){for(let a=0;a<f;a++)Oe(t,a,f,e,r,o,n);for(let a=0;a<f;a++)Oe(t,a*f,1,e,r,o,n)}function Oe(t,e,r,o,n,a,i){n[0]=0,a[0]=-i,a[1]=i,o[0]=t[e];for(let s=1,l=0,u=0;s<f;s++){o[s]=t[e+s*r];let c=s*s;do{let v=n[l];u=(o[s]-o[v]+c-v*v)/(s-v)/2}while(u<=a[l]&&--l>-1);l++,n[l]=s,a[l]=u,a[l+1]=i}for(let s=0,l=0;s<f;s++){for(;a[l+1]<s;)l++;let u=n[l],c=s-u;t[e+s*r]=o[u]+c*c}}var le=new Map;function Be(t){let e=le.get(t);return e||(e=gt(xt(t)).then(r=>{let o=wt(r,r.naturalWidth||f,r.naturalHeight||f);return{canvas:o,sdf:yt(o)}}),le.set(t,e),e.catch(()=>le.delete(t))),e}var St=`#version 300 es
in vec2 aPos;
void main() { gl_Position = vec4(aPos, 0.0, 1.0); }`,Rt=`#version 300 es
precision highp float;
out vec4 outColor;

uniform vec2 uCenter;      // device px, GL coords
uniform float uTile;       // tile size, device px
uniform sampler2D uSdf;    // signed distance, texture units, + outside
uniform sampler2D uCol;    // premultiplied colour, mipmapped
uniform float uTexSize;
uniform float uBoxFrac;

uniform float uPlateScale; // plate size relative to the tile
uniform float uShapeN;     // superellipse exponent: 2 = circle
uniform float uCornerN;    // final exponent, used by the ghost
uniform float uOptics;     // 1 = full refraction, 0 = flat
uniform float uPlateAlpha; // 1 = glass shown, 0 = bare logo
uniform float uLogoHalf;   // logo half size in plate units (zoom included)
uniform vec2 uLogoOff;     // logo centre, plate units
uniform float uBold;       // stroke swell, in logo half-size units
uniform float uBlur;       // edge softness, plate units
uniform float uFrost;      // milky lift inside a young bubble
uniform float uDome;       // lens bulge height
uniform float uDrop;       // 1 while the glass is a round droplet, 0 once it has spread into the tile
uniform float uPinch;      // the face's stretch toward its corners, at the rim
uniform float uTilt;       // extra stretch of the rising diagonal's corners (0\u20131)
uniform float uRim;
uniform float uHalo;
uniform float uShadow;
uniform float uGhost;
uniform float uRipR;       // ripple radius, plate sizes
uniform float uRipA;
uniform float uBare;       // 1 once the logo may show without glass (the ending)
uniform float uReach;      // the rim band's full width, plate units
uniform float uCornerPull; // how much harder the corners pull than the sides
uniform float uStreak;     // how far a corner smears content along the rim, in band widths
uniform float uWiden;      // how much wider the folding band grows toward the corners
uniform float uSlab;       // how far the slab stands above the logo, plate units
uniform float uEtaSpread;  // index spread across the spectrum (red highest)
uniform float uFocus;      // how far in along the diagonal a corner focuses, plate units
uniform float uFocusK;     // how quickly the view slides back from the focus across the band
uniform float uFocusSplit; // how much further in red meets than violet, plate units
uniform float uRimLine;    // how far across the band the sight line takes to turn in to the focus
uniform float uCornerOn;   // 0 while the glass is round, 1 once it has spread into the tile
uniform float uDissolve;   // 0 \u2192 1 as the glass lets go of the logo
uniform float uGlow;       // colour bleed in the rim, plate units on screen
uniform float uFaceDisp;   // lateral colour across the face
uniform float uVivid;      // chroma lift of the dispersed light

uniform float uDisp;
uniform float uDouble;
uniform float uBevelW;
uniform float uSpec;
uniform float uIconPlate;
uniform float uUseColor;
uniform float uLightScene; // 1 = light backdrop, 0 = dark
uniform float uLightGlass; // the same for what the glass sits on (the plate, when there is one)
uniform float uKeep;       // 1 = the glass settles into a flat plate instead of letting go of it
uniform float uSheen;      // strength of the light band crossing the face
uniform float uSweep;      // where that band is, plate sizes along its diagonal
uniform float uLightAng;   // how far the rim light has turned, radians

uniform vec3 uBg;
uniform vec3 uPlateCol;
uniform vec3 uLogoCol;

float px; // one device pixel in plate units

vec2 rot(vec2 v, float a) { float c = cos(a), s = sin(a); return vec2(c * v.x - s * v.y, s * v.x + c * v.y); }

// aa: footprint of one screen pixel at q, plate units.
vec4 logoAt(vec2 q, float blur, float aa) {
  float L = uLogoHalf;
  float k = 0.5 * uBoxFrac / L;
  vec2 uv = vec2(0.5 + (q.x - uLogoOff.x) * k, 0.5 - (q.y - uLogoOff.y) * k);
  float d = texture(uSdf, uv).r / k;
  float w = 0.75 * aa + blur;
  float a = 1.0 - smoothstep(-w, w, d - uBold * L);
  vec3 c = uLogoCol;
  if (uUseColor > 0.5) {
    float lod = log2(max(1.0, w * k * uTexSize));
    vec4 c0 = textureLod(uCol, uv, lod);
    vec4 c1 = textureLod(uCol, uv, lod + 3.0);
    vec4 c2 = textureLod(uCol, uv, 7.0);
    c = c2.rgb / max(c2.a, 1e-4);
    c = mix(c, c1.rgb / max(c1.a, 1e-4), smoothstep(0.0, 0.06, c1.a));
    c = mix(c, c0.rgb / max(c0.a, 1e-4), smoothstep(0.02, 0.3, c0.a));
  }
  return vec4(c, a);
}

// Superellipse field. Returns signed distance (plate units, \u2212 inside); g = 1 on the rim.
float shape(vec2 p, float scale, float n, out vec2 nOut, out float g, out vec2 dg) {
  vec2 pp = p / scale;
  vec2 a = max(abs(pp), vec2(1e-6));
  g = pow(pow(a.x, n) + pow(a.y, n), 1.0 / n);
  dg = sign(pp) * pow(a, vec2(n - 1.0)) * pow(max(g, 1e-6), 1.0 - n);
  float dgl = max(length(dg), 1e-6);
  nOut = dg / dgl;
  return (g - 1.0) / dgl * scale;
}

// Curvature radius (plate units) of the shape's contour through p.
float contourRadius(vec2 p, float scale, float n) {
  vec2 a = max(abs(p / scale), vec2(1e-4));
  vec2 a1 = pow(a, vec2(n - 1.0));
  vec2 a2 = pow(a, vec2(n - 2.0));
  float k = (n - 1.0) * (a2.x * a1.y * a1.y + a2.y * a1.x * a1.x) / pow(max(dot(a1, a1), 1e-30), 1.5);
  return scale / max(k, 1e-3);
}

// Where the glass at x = s / bwF across its rounded edge looks: a slab uSlab above the logo with a
// quarter-round edge of radius bwF. A straight-down sight line bends inward by Snell's law, so the
// outer rim looks deepest and the view eases back to the face across the edge.
vec2 refractSample(float x, float bwF, float eta, float R, vec2 dirOut, vec2 p, float dome, float offMul) {
  float u = clamp(1.0 - x, 0.0, 0.995);
  float th = asin(u), thr = asin(u / eta);
  float z = uSlab + bwF * sqrt(1.0 - u * u);
  float off = offMul * z * tan(th - thr);
  off = off / (1.0 + off / (6.0 * R));
  return p - (dirOut * off + p * dome) * uOptics;
}

float gauss(float x, float c, float w) { float d = (x - c) / w; return exp(-0.5 * d * d); }
float band(float x, float a, float b, float w) { return smoothstep(a - w, a, x) * (1.0 - smoothstep(b, b + w, x)); }

// Visible spectrum, red (0) to violet (1).
float bump(float x, float c, float w) { float d = (x - c) / w; return exp(-0.5 * d * d); }
vec3 spectrum(float x) {
  return vec3(bump(x, 0.34, 0.2) + 0.08 * bump(x, 0.93, 0.05), bump(x, 0.58, 0.1), bump(x, 0.8, 0.11));
}

float hash(vec2 p) { return fract(sin(dot(p, vec2(12.9898, 78.233))) * 43758.5453); }

void main() {
  px = 2.0 / uTile;
  vec2 p = (gl_FragCoord.xy - uCenter) * px;

  vec4 lg = logoAt(p, uBlur, px);
  vec3 plain = mix(uBg, lg.rgb, lg.a * uBare);

  vec2 nOut, dg; float g;
  float sd = shape(p, uPlateScale, uShapeN, nOut, g, dg);
  float s = -sd;
  float bw = max(uBevelW, 0.004) * uPlateScale;
  float x = clamp(s / bw, 0.0, 1.0);
  float R = contourRadius(p, uPlateScale, uShapeN);
  vec2 pq = p * p;
  float diag = 4.0 * pq.x * pq.y / max((pq.x + pq.y) * (pq.x + pq.y), 1e-6);
  float tilt = mix(1.0 - uTilt, 1.0, smoothstep(-0.02, 0.02, p.x * p.y));
  float pinchPart = uPinch * min(g * g, 1.0) * diag * diag * tilt;
  float dome = uDome * (1.0 - min(g * g, 1.0)) + pinchPart;
  vec2 dirOut = normalize(mix(nOut, p / max(length(p), 1e-4), 0.2));
  // Rounded corners curve both ways, so they draw content in from deeper than the sides.
  float cornerness = max(smoothstep(0.1, 0.9, 4.0 * nOut.x * nOut.x * nOut.y * nOut.y), smoothstep(0.15, 0.75, diag));
  float offMul = 1.0 + 0.4 * max(uCornerPull - 1.0, 0.0) * tilt * cornerness * uCornerOn;
  // Around a corner every sight line meets at one focus a little way in along the diagonal.
  vec2 focus = sign(p) * (pow(0.5, 1.0 / uShapeN) - uFocus * 0.70710678) * uPlateScale;
  float focusW = tilt * cornerness * uOptics * uCornerOn;
  float bwF = max(uReach, 0.004) * (1.0 + uWiden * tilt * cornerness * uCornerOn);
  float xf = clamp(s / bwF, 0.0, 1.0);
  // Footprint of one pixel after refraction, measured in uniform control flow.
  vec2 qc = refractSample(xf, bwF, 1.5, R, dirOut, p, dome, offMul);
  float foot = max(max(length(dFdx(qc)), length(dFdy(qc))), 0.25 * px);

  // Backdrop: anticipation ghost, ripple, soft lift shadow and glow.
  vec3 bg = uBg;
  vec3 lift = mix(uBg + vec3(0.06), mix(uBg, vec3(1.0), 0.55), uLightScene);
  if (uGhost > 0.001) {
    vec2 gn, gdg; float gg;
    float gsd = shape(p, 1.0, uCornerN, gn, gg, gdg);
    bg = mix(bg, lift, uGhost * 0.12 * (1.0 - smoothstep(-0.16, 0.14, gsd)));
    bg *= 1.0 - uGhost * 0.03 * uLightScene * exp(-max(gsd, 0.0) / 0.12) * step(0.0, gsd);
  }
  float outside = max(sd, 0.0);
  if (uRipA > 0.001) {
    float d0 = (uRipR - 1.0) * uPlateScale;
    float rx = (sd - d0) / 0.022;
    float ring = exp(-rx * rx);
    bg += uRipA * ring * (0.04 * (0.55 + 0.45 * dot(nOut, normalize(vec2(-0.5, 0.8))))) * mix(0.5, 1.0, uLightScene);
    bg -= uRipA * 0.016 * uLightScene * exp(-(rx - 1.6) * (rx - 1.6));
  }
  float shadowFall = max(sd, 0.0) / (0.9 * uPlateScale);
  bg *= 1.0 - uShadow * 0.03 * exp(-shadowFall * shadowFall) * step(0.0, sd);
  vec3 haloCol = mix(vec3(0.62, 0.69, 0.80), vec3(1.0), uLightScene);
  bg = mix(bg, haloCol, clamp(uHalo * (0.30 * exp(-outside / (0.025 * uPlateScale)) + 0.07 * exp(-outside / (0.12 * uPlateScale))), 0.0, 1.0) * step(0.0, sd));

  vec3 col = bg;
  float soft = px + uBlur * 0.8 + 0.06 * uDissolve * (1.0 - uKeep) * uPlateScale;
  if (sd < soft) {
    // Lighting surface: a superellipse quarter, flat toward the face and steep at the rim.
    float y1 = 1.0 - x;
    const float K = 2.6;
    float base1 = max(1.0 - pow(y1, K), 1e-4);
    float db = min(pow(y1, K - 1.0) * pow(base1, 1.0 / K - 1.0), 25.0);
    // A second, lower step just inside the first draws the faint inner line.
    float s1 = bw * 0.62;
    float w2 = bw * 0.22;
    float t2 = clamp((s - s1) / w2, -1.0, 1.0);
    float dh2 = uDouble * bw * 0.16;
    float dd = dh2 * 0.5 * cos(t2 * 1.5707963) * 1.5707963 / w2 * step(abs(t2), 0.999);
    vec2 gDome = -uDome * 2.0 * g * dg * step(g, 1.0);
    vec2 grad = -(db + dd) * nOut + gDome;

    vec3 back = mix(uBg, uPlateCol, uIconPlate);
    vec3 liftG = mix(back + vec3(0.06), mix(back, vec3(1.0), 0.55), uLightGlass);
    float rblur = uBlur + 0.05 * length(qc - p) + min(uGlow * uOptics * (1.0 - xf) * foot / px, 0.04);

    // Each wavelength refracts by its own index, so everything the edge draws in fans into colour
    // while the face stays crisp. Around a corner the samples also smear along the rim.
    float cornerW = smoothstep(0.1, 0.9, 4.0 * nOut.x * nOut.x * nOut.y * nOut.y);
    float streak = 0.35 * uStreak * bw * mix(0.15, 1.0, cornerW) * pow(1.0 - xf, 1.5) * uOptics;
    vec2 tangent = vec2(-nOut.y, nOut.x);
    vec3 acc = vec3(0.0), wsum = vec3(0.0);
    for (int i = 0; i < 20; i++) {
      float lam = (float(i) + 0.5) / 20.0;
      float c = uDisp * (1.0 - 2.0 * lam);
      vec2 along = tangent * (streak * 2.0 * (fract(float(i) * 0.618034 + 0.31) - 0.5));
      float cf = uDisp * (1.0 - 2.0 * lam) * (lam > 0.5 ? 1.0 : 0.5);
      vec2 sp = refractSample(xf, bwF, 1.5 + uEtaSpread * c, R, dirOut, p + along,
                              dome + pinchPart * 0.3 * c, offMul);
      vec2 focusL = focus - sign(p) * (0.70710678 * uFocusSplit * c * uPlateScale);
      float wFocus = pow(1.0 - xf, uFocusK) * smoothstep(0.0, uRimLine * (1.0 + 0.6 * c), xf);
      sp = mix(sp, mix(p + along, focusL, wFocus), focusW);
      float faceOnly = smoothstep(0.7, 1.0, xf) * uOptics;
      sp *= 1.0 + uFaceDisp * cf * faceOnly;
      vec4 l = logoAt(sp, rblur + 0.12 * streak + uFaceDisp * 0.5 * max(c, 0.0) * faceOnly, foot);
      vec3 w = spectrum(lam);
      acc += mix(back, l.rgb, l.a) * w;
      wsum += w;
    }
    vec3 trans = acc / wsum;
    float tl = dot(trans, vec3(0.2126, 0.7152, 0.0722));
    trans = clamp(tl + (trans - tl) * (1.0 + uVivid * uOptics), 0.0, 1.0);
    // A young droplet is milky; the haze only ever lightens.
    float hazeLum = dot(trans, vec3(0.2126, 0.7152, 0.0722));
    float hazeGate = mix(1.0 - smoothstep(0.25, 0.75, hazeLum), smoothstep(0.25, 0.75, hazeLum), uLightGlass);
    trans = mix(trans, liftG, uFrost * 0.45 * hazeGate);

    float glassAmt = pow(1.0 - uDissolve, 1.5);
    float lit = uSpec * glassAmt;
    vec3 rimCol = mix(vec3(0.80, 0.87, 0.97), vec3(1.0), uLightGlass);

    // Light backdrop: the thick edge glows softly white over a clear face, with a hairline that is
    // bright along the top and right and a thin dark silhouette down the left and bottom.
    float sc = uPlateScale;
    float tLum = dot(trans, vec3(0.2126, 0.7152, 0.0722));
    float lightOnly = smoothstep(0.35, 0.85, tLum);
    float hw = smoothstep(-0.85, 0.5, dot(nOut, rot(vec2(0.5, 0.866), uLightAng)));
    float tileBand = band(s, 0.016 * sc, 0.075 * sc, 0.022 * sc);
    float dropBand = (1.0 - smoothstep(0.06 * sc, 0.13 * sc, s)) * smoothstep(0.0, 0.004 * sc, s);
    float glow = mix(0.32 * tileBand, 0.75 * dropBand, uDrop) * lightOnly;
    float edgeLine = gauss(s, 0.005 * sc, 0.0045 * sc);
    float lip = gauss(s, 0.15 * sc, 0.007 * sc) * uDouble * (1.0 - uDrop);
    vec3 lightGlass = mix(trans, vec3(1.0), glow * glassAmt);
    lightGlass += (0.075 * hw * edgeLine + 0.06 * (0.4 + 0.6 * hw) * lip) * lit;
    lightGlass *= 1.0 - 0.05 * (1.0 - hw) * edgeLine * glassAmt * (1.0 - uDrop);
    lightGlass = mix(lightGlass, vec3(1.0), 0.55 * uDrop * glassAmt * edgeLine);

    // Dark backdrop: a cool rim light that grows toward the steep edge, and a small key highlight.
    vec3 Nl = normalize(vec3(-grad, 1.0));
    float edge = 1.0 - Nl.z;
    vec2 ldir = rot(normalize(vec2(-0.62, 0.78)), uLightAng);
    float side = dot(nOut, ldir);
    float fres = pow(edge, 1.5);
    vec3 rim = rimCol * fres * (0.35 + 0.65 * max(side, -side * 0.8)) * uRim * 0.65;
    vec3 Hv = normalize(normalize(vec3(-0.45, 0.6, 0.66)) + vec3(0.0, 0.0, 1.0));
    float spc = pow(max(dot(Nl, Hv), 0.0), 140.0) * 0.8 * smoothstep(0.0, 0.25, y1);
    vec3 darkGlass = trans * (1.0 - 0.25 * fres) + (rim + vec3(spc)) * lit;
    darkGlass = mix(darkGlass, rimCol, uDrop * 0.4 * uSpec * (1.0 - smoothstep(0.0, 0.1 * uPlateScale, s)));
    vec3 glass = mix(darkGlass, lightGlass, uLightGlass);

    // While the glass holds the logo a soft band of light crosses the face, brightest near the rim.
    float sweepD = dot(p / uPlateScale, normalize(vec2(0.8, 0.6))) - uSweep;
    float sheen = uSheen * glassAmt * exp(-sweepD * sweepD / 0.03) * (0.55 + 0.45 * (1.0 - x));
    glass = mix(glass, vec3(1.0), sheen * mix(0.22, 0.42, uLightGlass));

    float cov = clamp(0.5 - sd / soft, 0.0, 1.0);
    col = mix(bg, glass, cov);
  }

  vec3 outc = mix(plain, col, uPlateAlpha);
  outc += (hash(gl_FragCoord.xy) - 0.5) / 255.0;
  outColor = vec4(outc, 1.0);
}`;function Fe(t){let e=t.getContext("webgl2",{antialias:!1,premultipliedAlpha:!1});if(!e)return null;let r=(p,b)=>{let w=e.createShader(p);if(e.shaderSource(w,b),e.compileShader(w),!e.getShaderParameter(w,e.COMPILE_STATUS))throw new Error(e.getShaderInfoLog(w)||"shader");return w},o=e.createProgram();if(e.attachShader(o,r(e.VERTEX_SHADER,St)),e.attachShader(o,r(e.FRAGMENT_SHADER,Rt)),e.linkProgram(o),!e.getProgramParameter(o,e.LINK_STATUS))throw new Error(e.getProgramInfoLog(o)||"program");e.useProgram(o),e.bindBuffer(e.ARRAY_BUFFER,e.createBuffer()),e.bufferData(e.ARRAY_BUFFER,new Float32Array([-1,-1,3,-1,-1,3]),e.STATIC_DRAW);let n=e.getAttribLocation(o,"aPos");e.enableVertexAttribArray(n),e.vertexAttribPointer(n,2,e.FLOAT,!1,0,0);let a={},i=e.getProgramParameter(o,e.ACTIVE_UNIFORMS);for(let p=0;p<i;p++){let b=e.getActiveUniform(o,p);a[b.name]=e.getUniformLocation(o,b.name)}let s=e.createTexture(),l=e.createTexture();e.uniform1i(a.uSdf,0),e.uniform1i(a.uCol,1);let u=!1,c=p=>{e.texParameteri(e.TEXTURE_2D,e.TEXTURE_MIN_FILTER,p),e.texParameteri(e.TEXTURE_2D,e.TEXTURE_MAG_FILTER,e.LINEAR),e.texParameteri(e.TEXTURE_2D,e.TEXTURE_WRAP_S,e.CLAMP_TO_EDGE),e.texParameteri(e.TEXTURE_2D,e.TEXTURE_WRAP_T,e.CLAMP_TO_EDGE)};function v(p){e.activeTexture(e.TEXTURE0),e.bindTexture(e.TEXTURE_2D,s),e.pixelStorei(e.UNPACK_PREMULTIPLY_ALPHA_WEBGL,!1),e.texImage2D(e.TEXTURE_2D,0,e.R16F,f,f,0,e.RED,e.FLOAT,p.sdf),c(e.LINEAR),e.activeTexture(e.TEXTURE1),e.bindTexture(e.TEXTURE_2D,l),e.pixelStorei(e.UNPACK_PREMULTIPLY_ALPHA_WEBGL,!0),e.texImage2D(e.TEXTURE_2D,0,e.RGBA8,e.RGBA,e.UNSIGNED_BYTE,p.canvas),e.pixelStorei(e.UNPACK_PREMULTIPLY_ALPHA_WEBGL,!1),e.generateMipmap(e.TEXTURE_2D),c(e.LINEAR_MIPMAP_LINEAR),u=!0}function g(p,b,w,L){if(u){e.viewport(0,0,b,w),e.uniform2f(a.uCenter,b/2,w/2),e.uniform1f(a.uTile,L),e.uniform1f(a.uTexSize,f),e.uniform1f(a.uBoxFrac,B);for(let E in p){let C=p[E];typeof C=="number"&&a[E]&&e.uniform1f(a[E],C)}e.uniform3fv(a.uBg,p.uBg),e.uniform3fv(a.uPlateCol,p.uPlateCol),e.uniform3fv(a.uLogoCol,p.uLogoCol),e.uniform2fv(a.uLogoOff,p.uLogoOff),e.drawArrays(e.TRIANGLES,0,3)}}function x(){e.getExtension("WEBGL_lose_context")?.loseContext()}function _(p){e.activeTexture(e.TEXTURE1),e.bindTexture(e.TEXTURE_2D,l),e.pixelStorei(e.UNPACK_PREMULTIPLY_ALPHA_WEBGL,!0),e.texImage2D(e.TEXTURE_2D,0,e.RGBA8,e.RGBA,e.UNSIGNED_BYTE,p),e.pixelStorei(e.UNPACK_PREMULTIPLY_ALPHA_WEBGL,!1),e.generateMipmap(e.TEXTURE_2D)}return{setLogo:v,setColor:_,render:g,dispose:x}}var Et=1.1,se=.5,Lt=t=>t.present+Et,j=t=>t<0?0:t>1?1:t,I=(t,e,r)=>t+(e-t)*r,S=(t,e,r)=>{let o=j((r-t)/(e-t));return o*o*(3-2*o)},ie=(t,e,r)=>{let o=j((r-t)/(e-t));return o*o*o*(o*(o*6-15)+10)};function $(t){let e=t.replace("#","");e.length===3&&(e=e.replace(/./g,"$&$&"));let r=parseInt(e.slice(0,6),16)||0;return[(r>>16&255)/255,(r>>8&255)/255,(r&255)/255]}var Me=([t,e,r])=>.2126*t+.7152*e+.0722*r;function A(t,e,r){if(t<=0)return 0;let o=2*Math.PI/e;if(r>=1)return 1-Math.exp(-o*t)*(1+o*t);let n=o*Math.sqrt(1-r*r);return 1-Math.exp(-r*o*t)*(Math.cos(n*t)+r*o/n*Math.sin(n*t))}var De=new Map;function Pe(t,e,r){let o=`${t}/${e}/${r}`,n=De.get(o);if(n===void 0){let a=0,i=3;for(let s=0;s<40;s++){let l=(a+i)/2;A(l,e,r)<t?a=l:i=l}De.set(o,n=i)}return n}function Ct(t,e,r=0){let o=e.present,n=e.keepPlate?1:0,a=1-e.bounce,i=A(t+.01,e.response,a),s=Pe(.85,e.response,a)-.01,l=Pe(.92,e.response,a)-.01,u=A(t-l,.4,1),c=1-S(.05,1,u),v=S(0,.08,t),g=e.drift*A(t-.3,2.2,1),x=.25*A(t,.7,1)+.75*ie(0,e.glide,t),_=A(t-.5,2.4,1),p=A(t-o,.95,1),b=A(t-o-.05,.65,1),w=.15*e.bulge*(1-S(.4,.95,i)),L=(1+(e.startZoom-1)*(1-x))*(1-.045*_)*I(1,e.finalScale,p)*(1-.06*r),E=I(e.bevelWidth,Math.max(e.bevelWidth,.4),c),C=I(e.startSize,1,i)*(1+g)*(1+.14*b*(1-n))*(1-n*(.03*b+.06*r)),h=$(e.background);return{uPlateScale:C,uShapeN:I(2,e.corner,u),uCornerN:e.corner,uOptics:1-S(.55,1,b),uPlateAlpha:n?v*(1-r):v*(1-S(.45,1,b)),uLogoHalf:e.logoScale*L,uLogoOff:[e.logoOffset[0]*L,e.logoOffset[1]*L],uKeep:n,uSheen:e.sheen,uSweep:I(-1.6,1.6,ie(.9,o-.1,t)),uLightAng:e.lightTurn*ie(.4,o+.4,t),uBold:e.swell*.03*(1-x),uBlur:e.focus*.05*(1-S(.3,.95,i))+.03*r,uFrost:e.focus*(1-S(.5,.95,i)),uPinch:.38*e.stretch*S(.1,.9,u)*S(.75,.97,x),uTilt:e.tilt,uDome:w,uDrop:c,uRim:1+.8*c,uHalo:e.halo*(.5+.5*c)*(1-n*b),uShadow:Math.max(e.shadow*S(.45,.8,i)*(1-S(0,.6,u)),.8*e.shadow*n*b),uGhost:S(0,.03,t)*(1-S(.04,.08,t)),uRipR:1+.9*Math.max(0,t-s),uRipA:e.ripple*S(s,s+.06,t)*Math.exp(-Math.max(0,t-s)/.6),uBare:(1-n)*S(o-.25,o,t)*(1-r),uReach:E*C,uCornerPull:e.cornerPull,uStreak:e.edgeSmear,uWiden:e.cornerWidth,uSlab:.3*e.opticalDepth,uEtaSpread:.06,uFocus:e.cornerFocus,uFocusK:1,uFocusSplit:.056*e.colorBleed,uRimLine:.09,uCornerOn:S(.35,1,u),uGlow:.012*e.colorBleed,uFaceDisp:.012*e.dispersion,uVivid:.85,uDissolve:b,uDisp:e.dispersion,uDouble:e.doubleBevel,uBevelW:E*(1-b),uSpec:e.specular,uIconPlate:e.iconPlate?1:0,uUseColor:e.originalColors?1:0,uLightScene:Me(h)>.5?1:0,uLightGlass:Me(e.iconPlate?$(e.plateColor):h)>.5?1:0,uBg:h,uPlateCol:$(e.plateColor),uLogoCol:$(e.logoColor)}}function Ge(t,e){let r=document.createElement("canvas");r.setAttribute("aria-hidden","true"),r.style.cssText="position:absolute;inset:0;width:100%;height:100%;display:block",t.appendChild(r);let o=null;try{o=Fe(r)}catch(d){console.error(d)}if(!o)return r.remove(),null;let n=window.matchMedia("(prefers-reduced-motion: reduce)").matches,a=null,i=n?1.4:0,s=!n,l=0,u=0,c=!0,v=!1,g=!1,x=0,_=0,p=null;function b(d){x=0;let y=Math.min(.1,(d-_)/1e3);_=d;let{settings:F,loop:Ue,speed:qe,time:X,source:K,sourceScale:Ne}=e.current,ce=!!(K&&K.width>0&&a&&o&&!g);if(ce){p||(p=document.createElement("canvas"),p.width=p.height=f);let k=p.getContext("2d"),T=f*B/Math.max(.05,Ne);k.clearRect(0,0,f,f),k.drawImage(K,(f-T)/2,(f-T)/2,T,T),o.setColor(p),c=!0}let U=Lt(F);if(X!==void 0)s=!1,i=X,u=j((X-U-Math.max(.05,F.hold))/se);else if(s&&a)if(l>0){l-=y;let k=u;u=j(1-l/se),l<=0&&(l=0,u=0,i=0),(u!==k||i===0)&&(c=!0)}else i+=y*qe,i>=U&&(i=U,Ue?l=Math.max(.05,F.hold)+se:s=!1),c=!0;if(c&&a&&o&&!g){let k=Math.min(window.devicePixelRatio||1,2),T=r.clientWidth,fe=r.clientHeight,Y=Math.max(1,Math.round(T*k)),Z=Math.max(1,Math.round(fe*k));(r.width!==Y||r.height!==Z)&&(r.width=Y,r.height=Z);let We=Math.min(F.tileSize,Math.min(T,fe)/1.75);o.render(Ct(Math.min(i,U),F,u),Y,Z,We*k),c=!1}v&&(s||ce)&&a&&!g&&(x=requestAnimationFrame(b))}function w(){x||!v||g||(_=performance.now(),x=requestAnimationFrame(b))}let L=new IntersectionObserver(([d])=>{v=d.isIntersecting,v?w():x&&(cancelAnimationFrame(x),x=0)});L.observe(t);let E=new ResizeObserver(()=>{c=!0,w()});E.observe(t);let C=d=>{d.preventDefault(),g=!0},h=()=>{g=!1;try{o=Fe(r),o&&a&&o.setLogo(a)}catch(d){console.error(d)}c=!0,w()};return r.addEventListener("webglcontextlost",C),r.addEventListener("webglcontextrestored",h),{setLogo(d){a=d,o?.setLogo(d),n||(i=0,s=!0,l=0,u=0),c=!0,w()},replay(){i=0,s=!0,l=0,u=0,c=!0,w()},invalidate(){c=!0,w()},dispose(){x&&cancelAnimationFrame(x),L.disconnect(),E.disconnect(),r.removeEventListener("webglcontextlost",C),r.removeEventListener("webglcontextrestored",h),o?.dispose(),r.remove()}}}var G=document.documentElement,D=document.getElementById("intro"),ue=document.getElementById("orb");function O(t=!1){G.classList.contains("intro")&&(window.dispatchEvent(new Event("sorph:intro-done")),G.classList.remove("intro"),G.classList.add("intro-out"),D&&(D.style.transition=`opacity ${t?.2:.7}s ease`,D.style.opacity="0",setTimeout(()=>{D.remove(),G.classList.remove("intro-out")},1e3)))}window.sorphIntroFinish=O;function kt(){if(!D||!ue)return O(!0);let t=ue.getBoundingClientRect();if(!t.width)return O(!0);let e=.549,r={...Ie.light,background:"#ffffff",plateColor:"#ffffff",originalColors:!0,logoScale:.62,finalScale:1,startZoom:2.2,tileSize:0},o=.774;r.tileSize=o*e*t.width/(r.logoScale*r.finalScale*B);let n=Math.ceil(r.tileSize*1.75)+2,a=document.createElement("div"),i=t.left+t.width/2,s=t.top+t.height/2;a.style.cssText=`position:absolute;left:${i-n/2}px;top:${s-n/2}px;width:${n}px;height:${n}px;background:#fff;overflow:hidden`,D.appendChild(a);let u=Ge(a,{current:{settings:r,loop:!1,speed:1,time:void 0,source:ue,sourceScale:e}});if(!u)return O(!0);Be(new URL("app/orb.png",document.baseURI).href).then(c=>{u.setLogo(c),setTimeout(()=>O(),(r.present-.1)*1e3)},()=>O(!0))}if(G.classList.contains("intro")){requestAnimationFrame(()=>requestAnimationFrame(kt));let t=()=>O(!0);for(let e of["wheel","touchmove","keydown","pointerdown"])addEventListener(e,t,{once:!0,passive:!0})}})();
/*! Bundled license information:

react/cjs/react.production.min.js:
  (**
   * @license React
   * react.production.min.js
   *
   * Copyright (c) Facebook, Inc. and its affiliates.
   *
   * This source code is licensed under the MIT license found in the
   * LICENSE file in the root directory of this source tree.
   *)

react/cjs/react-jsx-runtime.production.min.js:
  (**
   * @license React
   * react-jsx-runtime.production.min.js
   *
   * Copyright (c) Facebook, Inc. and its affiliates.
   *
   * This source code is licensed under the MIT license found in the
   * LICENSE file in the root directory of this source tree.
   *)
*/
