import { Link } from 'react-router-dom';
import { ArrowRight } from 'lucide-react';
import { PublicHeader } from './Landing';

export default function AccessGuide() {
  return <div className="public-site"><PublicHeader/><main className="access-guide"><p className="eyebrow">INVITATION-ONLY ACCESS</p><h1>Access starts with authorization.</h1><p className="hero-intro">An official email address alone should not grant access to land-acquisition records. A designated department administrator must confirm the person's responsibility and approve their scope.</p>
    <ol className="access-steps">{[['Administrator invitation','Ask your department administrator for access. They verify your responsibility and send an invitation to your work email.'],['Verify identity and assignment','Verify the work email and confirm the department or agency relationship. The administrator assigns the role, state, district, and specific projects; applicants cannot grant themselves permissions.'],['Activate the approved account','Open the single-use invitation and choose a unique password of at least 12 characters. Your email is verified when you accept the invitation.'],['Enter the scoped workspace','Sign in to see only authorized records and aggregates. Account suspension and session revocation are enforced by the backend.']].map(([title,body],i) => <li key={title}><span>{i+1}</span><div><h2>{title}</h2><p>{body}</p></div></li>)}</ol>
    <section className="access-current"><h2>Ready for your invitation</h2><p>Once this instance is connected to Supabase and Brevo, your administrator can invite you by email. If your link expires, ask them to resend it. This page does not submit an access request.</p><p>Passwords are managed by Supabase Auth. Roles and jurisdiction assignments are stored in protected tables. Departmental SSO, MFA and self-service password recovery are not yet available.</p><Link className="button primary" to="/login">Go to sign in <ArrowRight size={15}/></Link></section>
    <Link className="back" to="/">← Return to LandGuard AI</Link>
  </main></div>;
}
