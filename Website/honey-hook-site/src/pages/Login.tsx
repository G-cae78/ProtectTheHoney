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
  const navigate = useNavigate();
  const { toast } = useToast();

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    
    if (email && password) {
      localStorage.setItem("userLoggedIn", "true");
      localStorage.setItem("userEmail", email);
      toast({
        title: "Login Successful",
        description: "Welcome back!",
      });
      navigate("/");
    } else {
      toast({
        title: "Login Failed",
        description: "Please enter both email and password.",
        variant: "destructive",
      });
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
              <Label htmlFor="email">Email</Label>
              <Input
                id="email"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="your@email.com"
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

            <Button type="submit" className="w-full">
              Sign In
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
                color: inherit;            /* match text color to background */
                text-decoration: none;     /* remove underline */
                opacity: 0;                /* make it fully transparent */
                pointer-events: auto;      /* still clickable */
                transition: opacity 0.2s ease;
              }
          
              .invisible-link a:focus {
                opacity: 1;                /* visible only if manually focused */
              }
          `}</style>
    </div>
  </>
  );
};

export default Login;
