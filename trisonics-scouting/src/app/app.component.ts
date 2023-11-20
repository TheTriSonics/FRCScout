import { Component, ViewChild } from '@angular/core';
import { Router } from '@angular/router';
import { BreakpointObserver, Breakpoints } from '@angular/cdk/layout';
import { UserDataService } from './services/user-data.service';
import { distinctUntilChanged, tap } from 'rxjs/operators';
import { MatSidenav } from '@angular/material/sidenav';


@Component({
  selector: 'app-root',
  templateUrl: './app.component.html',
  styleUrls: ['./app.component.scss']
})
export class AppComponent {
  title = 'trisonics-scouting-ng17';

  @ViewChild('sidenav', { static: true })
  public sidenav!: MatSidenav;

  public displayTeamKey: boolean = false;

  public fullDisplay: boolean = true;

  public sidenavOpen: boolean = false

  private defaultMediaQuery = '(min-width: 800px)';

  private readonly breakpoint$ = this.breakpointObserver.observe(
    [Breakpoints.Large, Breakpoints.Medium, Breakpoints.Small, Breakpoints.XSmall,
      Breakpoints.Tablet, this.defaultMediaQuery]
  ).pipe(
    tap(value => console.log(value)),
    distinctUntilChanged()
  );

  constructor(
    public userData: UserDataService,
    public media: BreakpointObserver,
    public breakpointObserver: BreakpointObserver,
    public router: Router,
  ) { }

  public ngOnInit(): void {
    this.breakpoint$.subscribe(() => {
      console.log('something');
      this.fullDisplay = false;
      if (this.breakpointObserver.isMatched(this.defaultMediaQuery)) {
        this.fullDisplay = true;
      }
      if (this.breakpointObserver.isMatched(Breakpoints.Large)) {
        this.fullDisplay = true;
      }
      if (this.breakpointObserver.isMatched(Breakpoints.Medium)) {
        this.fullDisplay = true;
      }
      if (this.breakpointObserver.isMatched(Breakpoints.Tablet)) {
        this.fullDisplay = false;
      }
      if (this.breakpointObserver.isMatched(Breakpoints.Small)) {
        this.fullDisplay = false;
      }
      if (this.breakpointObserver.isMatched(Breakpoints.XSmall)) {
        this.fullDisplay = false;
      }
      if (this.fullDisplay) {
        this.sidenavOpen = false;
      }
    });
  }

 public displaySidenavMenu(): void {
  this.sidenav.toggle();
 }

  public enableDisplayTeamKey(): void {
  }

  public goToSettings(): void {
  }
}
