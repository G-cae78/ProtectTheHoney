import { Button } from "@/components/ui/button";
import { Link } from "react-router-dom";
import { User, ShieldCheck } from "lucide-react";

const Navbar = () => {
  return (
    <nav className="fixed top-0 left-0 right-0 z-50 bg-background/80 backdrop-blur-md border-b border-border">
      <div className="container mx-auto px-4">
        <div className="flex items-center justify-between h-16">
          <Link to="/" className="text-2xl font-bold bg-gradient-honey bg-clip-text text-transparent">
            Pure Honey
          </Link>
          
          <div className="flex items-center gap-3">
            <Link to="/login">
              <Button variant="ghost" size="sm" className="gap-2">
                <User className="w-4 h-4" />
                Login
              </Button>
            </Link>
            <Link to="/admin">
              <Button variant="outline" size="sm" className="gap-2">
                <ShieldCheck className="w-4 h-4" />
                Admin
              </Button>
            </Link>
          </div>
        </div>
      </div>
    </nav>
  );
};

export default Navbar;
