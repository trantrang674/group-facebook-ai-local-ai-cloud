/* ===== LỚP DỮ LIỆU SUPABASE cho bản web (chèn bởi scripts/build_web_app.py; KHÔNG sửa tay trong docs/app.html) =====
   Ghi đè (theo quy tắc "khai báo hàm sau thắng") các hàm của dashboard cục bộ: api, runJob, sideCardItems.
   Giao diện phía trên giữ nguyên. Mọi quyền truy cập do RLS của Supabase quyết định, không phải mã ở đây. */
var RC=window.SITE_CONFIG||{},sb=null,READY=false,ME="";
function run(){return h("div")}  /* bản web không chạy lệnh agent: CÀI ĐẶT chỉ hiện nguồn dữ liệu */

function api(path,body){
 if(path==="/api/state")return rState();
 if(path==="/api/draft")return rDraft(body);
 if(path.indexOf("/api/report")===0)return rReport(path);
 return Promise.reject(new Error("Chức năng này chỉ có trên máy chủ chính."));
}
function runJob(){alert("Lệnh chạy agent (quét dữ liệu, /weekly, /daily) chỉ thực hiện trên máy chủ chính của chủ dự án. Kết quả sẽ tự xuất hiện ở đây sau khi đồng bộ.");return Promise.resolve()}
function sideCardItems(){return[
 h("div",{class:"st"},[h("span",{class:"dot ok"}),"Bản web · nhân viên"]),
 h("div",{class:"st",style:"word-break:break-all"},[h("span",{class:"dot ok"}),ME]),
 h("div",{class:"st"},[h("span",{class:"dot ok"}),"Giai đoạn 1 · 0% bán hàng"]),
 h("button",{onclick:function(){sb.auth.signOut()}},"Đăng xuất")]}

function chk(r){if(r.error)throw new Error(r.error.message);return r.data}
function localNow(){var d=new Date(),p=function(n){return(n<10?"0":"")+n};return iso(d)+"T"+p(d.getHours())+":"+p(d.getMinutes())+":"+p(d.getSeconds())}
function rState(){
 return Promise.all([
  sb.from("drafts").select("*").order("date").order("slot").limit(1000),
  sb.from("plans").select("*").order("src_mtime",{ascending:false}).limit(1),
  sb.from("topics").select("*").order("src_mtime",{ascending:false}).limit(12),
  sb.from("source_runs").select("*").order("collected_at",{ascending:false}).limit(1),
  sb.from("reports_internal").select("kind,period,title").order("period",{ascending:false}),
  sb.from("feedback").select("draft_id,feedback,created_at").order("created_at",{ascending:false}).limit(10)
 ]).then(function(rs){
  var dr=chk(rs[0]),pl=chk(rs[1])[0],tpAll=chk(rs[2]),tp=tpAll[0],sr=chk(rs[3])[0],rp=chk(rs[4]),fb=chk(rs[5]);
  var drafts=dr.map(function(r){var d=Object.assign({},r.extra||{},r);d._folder=r.folder;d.status=(r.folder==="sent"?"pending":r.folder);d.sources=r.sources||[];return d});
  return{now:localNow(),drafts:drafts,
   plan:pl?(pl.raw||{week:pl.week,range:pl.range,notes:pl.notes,slots:pl.slots,trial_today:pl.trial_today}):null,
   plan_file:pl?pl.week+".json":null,
   topics:{file:tp?tp.file+".json":null,items:tp?tp.items:[]},
   topics_all:tpAll.map(function(x){return{file:x.file+".json",items:x.items||[]}}),
   sources:sr?{date:sr.week,window:sr.window,collected_at:sr.collected_at,items:sr.items||[]}:{date:null,items:[]},
   serpapi:{used:0,budget:250,serper_used:0,serper_total:2500},
   reports:rp.map(function(r){return{kind:r.kind,name:r.period+".md"}}),
   feedback:fb.reverse().map(function(f){return{id:f.draft_id,feedback:f.feedback}}),
   env:{telegram:false,claude:true},job:{running:false,name:null,code:null,tail:""}}})}
function rReport(path){
 var q={};path.split("?")[1].split("&").forEach(function(x){var p=x.split("=");q[p[0]]=decodeURIComponent(p[1]||"")});
 return sb.from("reports_internal").select("body_md").eq("kind",q.kind).eq("period",(q.name||"").replace(/\.md$/,"")).single().then(function(r){return{text:chk(r).body_md}})}
function rDraft(b){
 var id=b.id,a=b.action,u={};
 if(typeof b.caption==="string")u.caption=b.caption.slice(0,20000);
 if(typeof b.caption_alt==="string")u.caption_alt=b.caption_alt.slice(0,20000);
 if(typeof b.post_url==="string"){var pu=b.post_url.trim();if(pu&&!/^https?:\/\/\S+$/.test(pu))return Promise.reject(new Error("Link phải bắt đầu bằng http:// hoặc https://"));u.post_url=pu}
 if(u.caption!==undefined||u.caption_alt!==undefined)u.edited=true;
 var cur=S.drafts.filter(function(d){return d.id===id})[0];
 if(!cur)return Promise.reject(new Error("Không thấy bài"));
 var chosen=cur.chosen,cap=(u.caption!==undefined?u.caption:cur.caption),alt=(u.caption_alt!==undefined?u.caption_alt:cur.caption_alt);
 if(a==="approve"){u.folder="approved";u.chosen=(b.variant==="B"&&alt)?"B":"A";u.final_caption=u.chosen==="B"?alt:cap}
 else if(a==="reject"){u.folder="rejected";u.reject_note=String(b.note||"").slice(0,1000)}
 else if(a==="posted"){u.folder="posted"}
 else if(a==="revert"){u.folder="pending"}
 else if(a==="edit"){if(chosen)u.final_caption=chosen==="B"?alt:cap}
 else return Promise.reject(new Error("Hành động không hợp lệ"));
 return sb.from("drafts").update(u).eq("id",id).select("id").then(function(r){
  var rows=chk(r);if(!rows.length)throw new Error("Không cập nhật được (không đủ quyền hoặc bài đã đổi).");
  if(a==="reject"&&u.reject_note)return sb.from("feedback").insert({draft_id:id,feedback:u.reject_note}).then(function(x){chk(x);return{ok:true}});
  return{ok:true}})}

﻿/* ----- đăng nhập bằng email + mật khẩu (tài khoản do chủ dự án tạo trong Supabase) + kiểm tra quyền nhân viên ----- */
var REC=/type=recovery/.test(location.hash||"");   /* mở từ link "Quên mật khẩu" trong email */
function lgShell(kids,foot){var g=document.getElementById("gate");g.style.display="flex";
 g.replaceChildren(h("div",{class:"lg"},[
  h("div",{class:"logo"},"AI"),
  h("h1",{},h("em",{},"CONTENT AI GROUP FB")),
  h("p",{class:"sub"},"Hệ thống nội bộ. Vui lòng đăng nhập để tiếp tục."),
  h("div",{class:"box"},kids),
  h("div",{class:"foot"},foot||"Kết nối được mã hóa. Dữ liệu chỉ hiển thị cho tài khoản đã được duyệt.")]))}
function pwField(id,ph){var inp=h("input",{type:"password",id:id,placeholder:ph||"",autocomplete:id==="lg-new"?"new-password":"current-password",required:"required"});
 var eye=h("button",{type:"button",title:"Hiện/ẩn mật khẩu",onclick:function(){inp.type=inp.type==="password"?"text":"password"}},"👁");
 return{input:inp,wrap:h("div",{class:"pw"},[inp,eye])}}
function showLoginGate(prefill,note){
 var email=h("input",{type:"email",id:"lg-email",autocomplete:"email",required:"required",value:prefill||""}),pw=pwField("lg-pw"),err=h("div",{class:"err",style:"display:none"}),ok=h("div",{class:"okm",style:"display:none"}),btn=h("button",{type:"submit",class:"go"},"Đăng nhập");
 if(note){ok.style.display="block";ok.textContent=note}
 var forgot=h("a",{class:"fg",onclick:function(){var em=email.value.trim();err.style.display="none";
   if(!em){err.style.display="block";err.textContent="Nhập email của bạn ở ô Email rồi bấm lại “Quên mật khẩu?”.";return}
   sb.auth.resetPasswordForEmail(em,{redirectTo:location.origin+location.pathname}).then(function(){ok.style.display="block";ok.textContent="Nếu email thuộc tài khoản nhân viên, bạn sẽ nhận được email hướng dẫn đặt lại mật khẩu."})}},"Quên mật khẩu?");
 var f=h("form",{onsubmit:function(e){e.preventDefault();err.style.display="none";btn.disabled=true;btn.textContent="Đang đăng nhập…";
   sb.auth.signInWithPassword({email:email.value.trim(),password:pw.input.value}).then(function(r){
    btn.disabled=false;btn.textContent="Đăng nhập";
    if(r.error){err.style.display="block";err.textContent="Email hoặc mật khẩu không đúng."}   /* thông báo chung, không lộ email nào tồn tại */
   })}},[
  h("label",{for:"lg-email"},"Email"),email,
  h("label",{for:"lg-pw",style:"margin-top:16px"},["Mật khẩu",forgot]),pw.wrap,
  err,ok,btn]);
 lgShell([f])}
function showNewPassword(){
 var a=pwField("lg-new","Mật khẩu mới (từ 10 ký tự)"),b=pwField("lg-new2","Nhập lại mật khẩu mới"),err=h("div",{class:"err",style:"display:none"}),btn=h("button",{type:"submit",class:"go"},"Lưu mật khẩu mới");
 var f=h("form",{onsubmit:function(e){e.preventDefault();err.style.display="none";
   if(a.input.value.length<10){err.style.display="block";err.textContent="Mật khẩu cần ít nhất 10 ký tự.";return}
   if(a.input.value!==b.input.value){err.style.display="block";err.textContent="Hai mật khẩu không khớp.";return}
   btn.disabled=true;
   sb.auth.updateUser({password:a.input.value}).then(function(r){btn.disabled=false;
    if(r.error){err.style.display="block";err.textContent="Không đặt được mật khẩu mới: "+r.error.message;return}
    REC=false;history.replaceState(null,"",location.pathname);
    sb.auth.getSession().then(function(s){if(s.data.session)enter(s.data.session.user);else showLoginGate()})})}},[
  h("label",{},"Mật khẩu mới"),a.wrap,h("label",{style:"margin-top:16px"},"Nhập lại"),b.wrap,err,btn]);
 lgShell([h("div",{style:"font-weight:700;margin-bottom:12px"},"Đặt mật khẩu mới"),f])}
function showDenied(user){lgShell([h("div",{style:"font-weight:700;margin-bottom:8px"},"Chưa được cấp quyền"),
 h("p",{class:"muted"},"Tài khoản "+user.email+" chưa nằm trong danh sách nhân viên. Hãy liên hệ chủ dự án."),
 h("button",{class:"go",type:"button",onclick:function(){sb.auth.signOut()}},"Đăng xuất")])}
function enter(user){
 sb.rpc("is_staff").then(function(r){
  if(r.data===true){READY=true;ME=user.email;document.getElementById("gate").style.display="none";load()}else showDenied(user)})}
function startRemote(){
 if(!window.supabase||!RC.SUPABASE_URL||/YOUR-/.test(RC.SUPABASE_URL+RC.SUPABASE_ANON_KEY)){lgShell([h("div",{style:"font-weight:700"},"Chưa cấu hình"),h("p",{class:"muted"},"Điền SUPABASE_URL và SUPABASE_ANON_KEY trong docs/config.js.")]);return}
 sb=window.supabase.createClient(RC.SUPABASE_URL,RC.SUPABASE_ANON_KEY,{auth:{persistSession:true,detectSessionInUrl:true}});
 sb.auth.getSession().then(function(r){var s=r.data&&r.data.session;
  if(REC&&s){showNewPassword();return}
  if(s)enter(s.user);else showLoginGate()});
 sb.auth.onAuthStateChange(function(ev,s){
  if(ev==="PASSWORD_RECOVERY"){REC=true;showNewPassword();return}
  if(ev==="SIGNED_IN"&&s&&!READY&&!REC)enter(s.user);
  if(ev==="SIGNED_OUT")location.reload()});
 setInterval(function(){if(READY&&!document.hidden)load(true)},60000)}
