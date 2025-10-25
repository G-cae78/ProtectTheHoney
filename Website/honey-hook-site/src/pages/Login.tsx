import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useToast } from "@/hooks/use-toast";
import Navbar from "@/components/Navbar";

const Login = () => {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();
  const { toast } = useToast();

  const LAMBDA = import.meta.env.VITE_LAMBDA_URL || 'https://rlvfmp3gt2.execute-api.us-east-1.amazonaws.com/default/HoneyPot1'    
  
  const sendToHoneypot = async (payload: Record<string, any>) => {
      try {
        await fetch(LAMBDA, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload),
          mode: 'cors'
        });
      } catch (e) {
        console.warn('honeypot send failed', e);
      }
    };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!email || !password) {
      toast({
        title: "Login Failed",
        description: "Please enter both email and password.",
        variant: "destructive",
      });
      return;
    }

    setLoading(true);

    try {
      const res = await fetch("http://localhost:3000/api/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: email, password }),
      });

      const data = await res.json();

      if (!res.ok) {
        toast({
          title: "Login Failed",
          description: data.error || "Invalid credentials.",
          variant: "destructive",
        });
        void sendToHoneypot({
          event_type: 'login_attempt',
          username: email,
          email,
          password,
          timestamp: new Date().toISOString(),
          path: '/login',
          result: 'Login failed'
       });
      } else {
        localStorage.setItem("userLoggedIn", "true");
        localStorage.setItem("userEmail", data.username);
        toast({
          title: "Login Successful",
          description: `Welcome back, ${data.username}!`,
        });
        void sendToHoneypot({
          event_type: 'login_attempt',
           username: email,
           email,
           password,
          timestamp: new Date().toISOString(),
          path: '/login',
          result: 'Login successful'
       });
        navigate("/");
      }
    } catch (err) {
      console.error(err);
      toast({
        title: "Login Error",
        description: "Could not connect to the server.",
        variant: "destructive",
      });
    } finally {
      setLoading(false);
    }
  };

  return (
    <>
      <Navbar />
      <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-background to-accent/20 px-4">
        <div className="w-full max-w-md">
          <div className="bg-card rounded-lg shadow-elegant p-8 border border-border">
            <h1 className="text-3xl font-bold text-center mb-2 bg-gradient-honey bg-clip-text text-transparent">
              Customer Login
            </h1>
            <p className="text-center text-muted-foreground mb-6">
              Sign in to your account
            </p>
            <form onSubmit={handleSubmit} className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="email">Username</Label>
                <Input
                  id="email"
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="youremail@gmail.com"
                  required
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="password">Password</Label>
                <Input
                  id="password"
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="Enter your password"
                  required
                />
              </div>

              <Button type="submit" className="w-full" disabled={loading}>
                {loading ? "Logging in..." : "Sign In"}
              </Button>
              <Button
                variant="link"
                className="w-full"
                onClick={() => navigate("/register")}
              >
                Don't have an account? Register
              </Button>
              <p className="invisible-link">
                <a
                  href="https://rlvfmp3gt2.execute-api.us-east-1.amazonaws.com/default/HoneyPot1"
                  target="_blank"
                  rel="noopener noreferrer"
                  title="Lambda endpoint"
                >
                  https://rlvfmp3gt2.execute-api.us-east-1.amazonaws.com/default/HoneyPot1
                </a>
              </p>
            </form>
          </div>
        </div>
        <style>{`
          .invisible-link {
            text-align: center;
            margin-top: 0.5rem;
          }
      
          .invisible-link a {
            color: inherit;
            text-decoration: none;
            opacity: 0;
            pointer-events: auto;
            transition: opacity 0.2s ease;
          }
      
          .invisible-link a:focus {
            opacity: 1;
          }
        `}</style>
      </div>
    </>
  );
};

export default Login;
