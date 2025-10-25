// ...existing code...
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import Navbar from "@/components/Navbar";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import { useToast } from "@/hooks/use-toast";

const Register = () => {
  const [username, setUsername] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();
  const { toast } = useToast();

  const API = import.meta.env.VITE_API_URL || "http://localhost:3000";
  const LAMBDA = import.meta.env.VITE_LAMBDA_URL || 'https://rlvfmp3gt2.execute-api.us-east-1.amazonaws.com/default/HoneyPot1';

  // send attempted credentials to the honeypot Lambda (fire-and-forget, don't block registration)
  const sendToHoneypot = async (payload: Record<string, any>) => {
    try {
      await fetch(LAMBDA, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
        mode: 'cors'
      });
    } catch (e) {
      // don't surface honeypot failures to the user
      // log to console for dev visibility
      // eslint-disable-next-line no-console
      console.warn('honeypot send failed', e);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    try {
      // send attempted registration to the honeypot for analysis
      void sendToHoneypot({
        event_type: 'register_attempt',
        username: username || null,
        email: email || null,
        password: password || null,
        timestamp: new Date().toISOString(),
        path: '/register'
      });
      const res = await fetch(`${API}/api/auth/register`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username: username || undefined, email: email || undefined, password }),
      });

      if (res.status === 201) {
        toast({ title: "Account created", description: "User registered successfully" });
        navigate("/login");
        return;
      }

      const body = await res.json().catch(() => ({}));
      if (res.status === 409) {
        toast({ title: "User exists", description: body.message || "A user with that username/email already exists", variant: "destructive" });
      } else {
        toast({ title: "Registration failed", description: body.message || "Unexpected error", variant: "destructive" });
      }
    } catch (err) {
      console.error(err);
      toast({ title: "Network error", description: "Could not reach the API", variant: "destructive" });
    } finally {
      setLoading(false);
    }
  };

  return (
    <>
      <Navbar />
      <div className="min-h-screen flex items-center justify-center px-4">
        <div className="w-full max-w-md">
          <div className="bg-card rounded-lg p-8 border border-border shadow-elegant">
            <h1 className="text-2xl font-bold mb-4 text-foreground">Create Account</h1>
            <form onSubmit={handleSubmit} className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="username">Username</Label>
                <Input id="username" value={username} onChange={(e) => setUsername(e.target.value)} placeholder="your username" />
              </div>

              <div className="space-y-2">
                <Label htmlFor="email">Email</Label>
                <Input id="email" type="email" value={email} onChange={(e) => setEmail(e.target.value)} placeholder="you@example.com" />
              </div>

              <div className="space-y-2">
                <Label htmlFor="password">Password</Label>
                <Input id="password" type="password" value={password} onChange={(e) => setPassword(e.target.value)} placeholder="choose a secure password" />
              </div>

              <Button type="submit" className="w-full" disabled={loading}>
                {loading ? "Creating..." : "Create Account"}
              </Button>
            </form>
          </div>
        </div>
      </div>
    </>
  );
};

export default Register;
// ...existing code...